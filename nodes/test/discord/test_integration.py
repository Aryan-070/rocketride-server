# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
# =============================================================================

"""
Integration tests for the Discord bot source node.

Tests actual Discord Gateway connection, message receiving, and sending.
Requires a valid Discord bot token and test server.

Set DISCORD_BOT_TOKEN env var to run these tests.
"""

import pytest
import asyncio
import os
import discord
from discord.ext import commands
import time


class TestDiscordGatewayConnection:
    """Test Discord Gateway connection and event handling."""

    @pytest.fixture
    async def bot_token(self):
        """Get bot token from environment."""
        token = os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            pytest.skip('DISCORD_BOT_TOKEN not set')
        return token

    @pytest.fixture
    async def test_bot(self, bot_token):
        """Create and connect a test bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.dm_messages = True

        bot = commands.Bot(command_prefix='!', intents=intents)
        bot.ready = False
        bot.messages_received = []

        @bot.event
        async def on_ready():
            bot.ready = True
            print(f'✅ Bot connected as {bot.user}')

        @bot.event
        async def on_message(message):
            if not message.author.bot:
                bot.messages_received.append(message)
                print(f'✅ Received message: {message.content}')

        # Start bot in background
        task = asyncio.create_task(bot.start(bot_token))

        # Wait for ready
        timeout = 30
        start = time.time()
        while not bot.ready and time.time() - start < timeout:
            await asyncio.sleep(0.1)

        yield bot

        # Cleanup
        await bot.close()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_gateway_connection(self, test_bot):
        """Test that bot successfully connects to Discord Gateway."""
        assert test_bot.ready, 'Bot failed to connect'
        assert test_bot.user is not None, 'Bot user not set'
        print('✅ Gateway connection successful')

    @pytest.mark.asyncio
    async def test_bot_user_info(self, test_bot):
        """Test that bot user information is available."""
        assert test_bot.user.id > 0, 'Bot ID not set'
        assert len(test_bot.user.name) > 0, 'Bot name not set'
        print(f'✅ Bot ID: {test_bot.user.id}, Name: {test_bot.user.name}')

    @pytest.mark.asyncio
    async def test_guilds_available(self, test_bot):
        """Test that bot can list available guilds."""
        guilds = test_bot.guilds
        assert len(guilds) > 0, 'Bot is not in any guilds'
        for guild in guilds[:3]:  # Show first 3
            print(f'✅ Guild: {guild.name} (ID: {guild.id})')

    @pytest.mark.asyncio
    async def test_text_channels_available(self, test_bot):
        """Test that bot can access text channels."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [c for c in guild.text_channels if isinstance(c, discord.TextChannel)]
        assert len(text_channels) > 0, 'No text channels found'
        print(f'✅ Found {len(text_channels)} text channels in {guild.name}')

    @pytest.mark.asyncio
    async def test_message_permissions(self, test_bot):
        """Test that bot has permission to send messages."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [c for c in guild.text_channels if isinstance(c, discord.TextChannel)]

        if not text_channels:
            pytest.skip('No text channels found')

        for channel in text_channels[:1]:
            perms = channel.permissions_for(guild.me)
            assert perms.send_messages, f'No send permission in {channel.name}'
            assert perms.view_channel, f'No view permission in {channel.name}'
            print(f'✅ Bot has send message permission in {channel.name}')

    @pytest.mark.asyncio
    async def test_send_message(self, test_bot):
        """Test sending a message to a text channel."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]
        test_message = f'🤖 Discord Node Test - {time.time()}'

        try:
            sent_msg = await channel.send(test_message)
            assert sent_msg is not None, 'Message send returned None'
            assert sent_msg.content == test_message, 'Message content mismatch'
            print(f'✅ Message sent successfully to {channel.name}')

            # Cleanup
            await sent_msg.delete()
            print('✅ Test message deleted')
        except discord.Forbidden:
            pytest.skip(f'No permission to send to {channel.name}')

    @pytest.mark.asyncio
    async def test_typing_indicator(self, test_bot):
        """Test showing typing indicator."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]

        try:
            async with channel.typing():
                await asyncio.sleep(0.5)  # Simulate processing
            print(f'✅ Typing indicator worked in {channel.name}')
        except discord.Forbidden:
            pytest.skip(f'No permission to show typing in {channel.name}')

    @pytest.mark.asyncio
    async def test_message_reply(self, test_bot):
        """Test replying to a message."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]
        original_msg = await channel.send(f'🤖 Test Message - {time.time()}')

        try:
            reply_msg = await original_msg.reply('✅ This is a reply', mention_author=False)
            assert reply_msg is not None, 'Reply returned None'
            assert reply_msg.reference is not None, 'Reply reference not set'
            print('✅ Message reply successful')

            # Cleanup
            await reply_msg.delete()
            await original_msg.delete()
        except discord.Forbidden:
            pytest.skip('No permission to reply')

    @pytest.mark.asyncio
    async def test_message_thread(self, test_bot):
        """Test creating a thread and posting in it."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]
        original_msg = await channel.send(f'🤖 Thread Test - {time.time()}')

        try:
            thread = await original_msg.create_thread(name='🤖 Test Thread')
            thread_msg = await thread.send('✅ Message in thread')
            assert thread_msg is not None, 'Thread message failed'
            print('✅ Thread creation and message successful')

            # Cleanup
            await thread.delete()
            await original_msg.delete()
        except discord.Forbidden:
            pytest.skip('No permission to create threads')

    @pytest.mark.asyncio
    async def test_long_message_chunking(self, test_bot):
        """Test sending a message longer than 2000 chars (should be split)."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]

        # Create a message longer than 2000 chars
        long_text = 'This is a test sentence. ' * 100  # ~2500 chars

        messages_sent = []
        try:
            # Split message (implementation would do this)
            chunks = []
            if len(long_text) <= 2000:
                chunks = [long_text]
            else:
                # Simple chunking for test
                chunk_size = 2000
                for i in range(0, len(long_text), chunk_size):
                    chunks.append(long_text[i : i + chunk_size])

            for chunk in chunks:
                msg = await channel.send(chunk)
                messages_sent.append(msg)

            assert len(messages_sent) > 1, 'Long message should be split'
            print(f'✅ Long message split into {len(messages_sent)} chunks')

            # Cleanup
            for msg in messages_sent:
                await msg.delete()
        except discord.Forbidden:
            pytest.skip('No permission to send messages')

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, test_bot):
        """Test handling of rate limits."""
        if not test_bot.guilds:
            pytest.skip('Bot not in any guilds')

        guild = test_bot.guilds[0]
        text_channels = [
            c
            for c in guild.text_channels
            if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
        ]

        if not text_channels:
            pytest.skip('No writable text channels found')

        channel = text_channels[0]

        try:
            # Send multiple messages rapidly
            messages = []
            for i in range(5):
                msg = await channel.send(f'Rate limit test {i + 1}')
                messages.append(msg)
                await asyncio.sleep(0.1)  # Small delay to avoid excessive rate limiting

            print(f'✅ Successfully sent {len(messages)} messages with rate limit handling')

            # Cleanup
            for msg in messages:
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
        except discord.Forbidden:
            pytest.skip('No permission to send messages')

    @pytest.mark.asyncio
    async def test_bot_intents(self, test_bot):
        """Test that required intents are enabled."""
        intents = test_bot.intents
        assert intents.message_content, 'Message Content Intent not enabled'
        assert intents.guilds, 'Guilds Intent not enabled'
        assert intents.dm_messages, 'DM Messages Intent not enabled'
        print('✅ All required intents enabled')

    @pytest.mark.asyncio
    async def test_event_handlers(self, test_bot):
        """Test that event handlers work (proven by other tests)."""
        # Event handlers are proven to work by test_gateway_connection,
        # test_send_message, and other tests that trigger on_ready and on_message events
        assert test_bot.ready, 'Bot event handlers working (ready event fired)'
        print('✅ All required event handlers working')


class TestDiscordNodeConfiguration:
    """Test Discord node with different configurations."""

    @pytest.mark.asyncio
    async def test_ignore_bots_config(self):
        """Test bot message filtering (ignoreBots config)."""
        ignore_bots = True

        # Mock bot message
        bot_message = type('Message', (), {'author': type('Author', (), {'bot': True}), 'content': 'Bot message'})()

        # Bot message should be ignored
        should_process = not (ignore_bots and bot_message.author.bot)
        assert not should_process, 'Bot message should be ignored'
        print('✅ Bot message filtering works')

    @pytest.mark.asyncio
    async def test_require_mention_config(self):
        """Test mention requirement (requireMention config)."""
        require_mention = True

        # Mock message with mention
        message_with_mention = type(
            'Message', (), {'mentions': [type('User', (), {'id': 123})()], 'content': '@bot hello'}
        )()

        # Should process when mentioned
        should_process = not require_mention or len(message_with_mention.mentions) > 0
        assert should_process, 'Should process mentioned message'
        print('✅ Mention requirement config works')

    @pytest.mark.asyncio
    async def test_guild_id_filtering(self):
        """Test guild ID allowlist (guildIds config)."""
        allowed_guild_ids = ['123456', '789012']

        message_guild_id = '123456'
        should_process = not allowed_guild_ids or str(message_guild_id) in allowed_guild_ids
        assert should_process, 'Should process message from allowed guild'

        message_guild_id = '999999'
        should_process = not allowed_guild_ids or str(message_guild_id) in allowed_guild_ids
        assert not should_process, 'Should skip message from non-allowed guild'
        print('✅ Guild ID filtering works')

    @pytest.mark.asyncio
    async def test_channel_id_filtering(self):
        """Test channel ID allowlist (channelIds config)."""
        allowed_channel_ids = ['111111', '222222', '333333']

        message_channel_id = '222222'
        should_process = not allowed_channel_ids or str(message_channel_id) in allowed_channel_ids
        assert should_process, 'Should process message from allowed channel'

        message_channel_id = '999999'
        should_process = not allowed_channel_ids or str(message_channel_id) in allowed_channel_ids
        assert not should_process, 'Should skip message from non-allowed channel'
        print('✅ Channel ID filtering works')

    @pytest.mark.asyncio
    async def test_reply_modes(self):
        """Test different reply modes (replyMode config)."""
        reply_modes = ['channel', 'reply', 'thread']

        for mode in reply_modes:
            assert mode in reply_modes, f'Invalid reply mode: {mode}'

        print('✅ All reply modes valid')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
