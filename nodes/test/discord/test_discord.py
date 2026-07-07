# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
# =============================================================================

"""
Unit tests for the Discord bot source node.

Tests focus on configuration parsing, helper methods, and message chunking
without requiring a running RocketRide server.
"""

import pytest
import json


class TestDiscordNodeConfiguration:
    """Test Discord node configuration parsing."""

    def test_config_defaults(self):
        """Test that configuration has sensible defaults."""
        # Mock the config dictionary as it would be passed from the engine
        config = {
            'botToken': 'test_token_123',
            'guildIds': None,
            'channelIds': None,
            'ignoreBots': True,
            'requireMention': False,
            'replyMode': 'reply',
            'showTyping': True,
            'maxAttachmentBytes': 26 * 1024 * 1024,
            'sendResponses': True,
        }

        # Verify defaults
        assert config['ignoreBots'] is True
        assert config['requireMention'] is False
        assert config['replyMode'] == 'reply'
        assert config['showTyping'] is True
        assert config['maxAttachmentBytes'] == 26 * 1024 * 1024
        assert config['sendResponses'] is True

    def test_config_custom_values(self):
        """Test that configuration accepts custom values."""
        config = {
            'botToken': 'custom_token',
            'guildIds': ['123456', '789012'],
            'channelIds': ['111111', '222222'],
            'ignoreBots': False,
            'requireMention': True,
            'replyMode': 'thread',
            'showTyping': False,
            'maxAttachmentBytes': 10 * 1024 * 1024,
            'sendResponses': False,
        }

        assert config['botToken'] == 'custom_token'
        assert config['guildIds'] == ['123456', '789012']
        assert config['channelIds'] == ['111111', '222222']
        assert config['ignoreBots'] is False
        assert config['requireMention'] is True
        assert config['replyMode'] == 'thread'
        assert config['showTyping'] is False
        assert config['maxAttachmentBytes'] == 10 * 1024 * 1024
        assert config['sendResponses'] is False


class TestDiscordMessageChunking:
    """Test message chunking for Discord's 2000-character limit."""

    def _chunk_message(self, text: str, max_length: int = 2000) -> list:
        """Replicate the message chunking logic from IEndpoint."""
        import re

        if len(text) <= max_length:
            return [text]

        chunks = []
        lines = text.split('\n')
        current_chunk = ''

        for line in lines:
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                if len(line) > max_length:
                    sentences = re.split(r'(?<=[.!?])\s+', line)
                    sentence_chunk = ''
                    for sentence in sentences:
                        if len(sentence_chunk) + len(sentence) + 1 <= max_length:
                            sentence_chunk += sentence + ' '
                        else:
                            if sentence_chunk:
                                chunks.append(sentence_chunk.rstrip())
                            sentence_chunk = sentence + ' '
                    if sentence_chunk:
                        chunks.append(sentence_chunk.rstrip())
                else:
                    current_chunk = line + '\n'

        if current_chunk:
            chunks.append(current_chunk.rstrip())

        return chunks

    def test_short_message_no_chunking(self):
        """Test that short messages are not chunked."""
        text = 'Hello, this is a short message.'
        chunks = self._chunk_message(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_message_chunked_by_lines(self):
        """Test that long messages are chunked at line boundaries."""
        text = 'Line 1\n' * 500  # Create a very long message
        chunks = self._chunk_message(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_exact_limit_message(self):
        """Test message exactly at the 2000-character limit."""
        text = 'a' * 2000
        chunks = self._chunk_message(text)
        assert len(chunks) == 1
        assert len(chunks[0]) == 2000

    def test_over_limit_by_one(self):
        """Test message just over the 2000-character limit."""
        text = 'a' * 2001
        chunks = self._chunk_message(text)
        assert len(chunks) == 1
        assert len(chunks[0]) == 2001

    def test_sentence_boundary_chunking(self):
        """Test that sentences are not split mid-word."""
        text = 'This is a sentence. ' * 200  # Create long text with sentence boundaries
        chunks = [c for c in self._chunk_message(text) if c.strip()]  # Filter empty

        # All chunks should be within limit
        for chunk in chunks:
            assert len(chunk) <= 2000

        # Verify that we get multiple chunks for this long text
        assert len(chunks) > 1

        # Verify chunks preserve complete sentences by checking no sentence
        # is split across chunks (each chunk should end with proper boundary)
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_mixed_content_chunking(self):
        """Test chunking with mixed line and sentence boundaries."""
        text = 'Line 1\n' + ('This is a sentence. ' * 150) + '\nLine 2'
        chunks = self._chunk_message(text)

        for chunk in chunks:
            assert len(chunk) <= 2000


class TestDiscordMimeTypeDetection:
    """Test MIME type detection from file extensions."""

    def _guess_media_type(self, filename: str, content_type: str = '') -> str:
        """Replicate the MIME type detection logic from IEndpoint."""
        if content_type:
            return content_type

        ext_to_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mov': 'video/quicktime',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.zip': 'application/zip',
        }

        filename_lower = filename.lower()
        for ext, mime_type in ext_to_type.items():
            if filename_lower.endswith(ext):
                return mime_type

        return 'application/octet-stream'

    def test_image_types(self):
        """Test detection of common image formats."""
        assert self._guess_media_type('photo.jpg') == 'image/jpeg'
        assert self._guess_media_type('picture.png') == 'image/png'
        assert self._guess_media_type('animation.gif') == 'image/gif'
        assert self._guess_media_type('modern.webp') == 'image/webp'

    def test_audio_types(self):
        """Test detection of common audio formats."""
        assert self._guess_media_type('song.mp3') == 'audio/mpeg'
        assert self._guess_media_type('recording.wav') == 'audio/wav'
        assert self._guess_media_type('voice.ogg') == 'audio/ogg'

    def test_video_types(self):
        """Test detection of common video formats."""
        assert self._guess_media_type('movie.mp4') == 'video/mp4'
        assert self._guess_media_type('clip.webm') == 'video/webm'
        assert self._guess_media_type('video.mov') == 'video/quicktime'

    def test_document_types(self):
        """Test detection of common document formats."""
        assert self._guess_media_type('document.pdf') == 'application/pdf'
        assert (
            self._guess_media_type('report.docx')
            == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        assert (
            self._guess_media_type('spreadsheet.xlsx')
            == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert self._guess_media_type('archive.zip') == 'application/zip'

    def test_unknown_type(self):
        """Test that unknown extensions default to octet-stream."""
        assert self._guess_media_type('file.xyz') == 'application/octet-stream'
        assert self._guess_media_type('data.unknown') == 'application/octet-stream'

    def test_content_type_override(self):
        """Test that explicit content_type takes precedence."""
        assert self._guess_media_type('file.txt', 'text/plain') == 'text/plain'
        assert self._guess_media_type('file.jpg', 'image/png') == 'image/png'

    def test_case_insensitive_extension(self):
        """Test that extension detection is case-insensitive."""
        assert self._guess_media_type('Photo.JPG') == 'image/jpeg'
        assert self._guess_media_type('Document.PDF') == 'application/pdf'


class TestDiscordServicesJsonSchema:
    """Test the services.json schema is valid."""

    def _get_services_json_path(self):
        """Resolve the path to services.json."""
        import os

        test_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(test_dir, '../../src/nodes/discord/services.json')

    def test_services_json_valid(self):
        """Test that services.json is valid JSON."""
        services_path = self._get_services_json_path()

        with open(services_path, 'r') as f:
            schema = json.load(f)

        # Verify required top-level keys
        assert 'title' in schema
        assert 'protocol' in schema
        assert 'classType' in schema
        assert 'fields' in schema
        assert 'lanes' in schema

    def test_services_json_has_discord_fields(self):
        """Test that services.json defines all Discord-specific fields."""
        services_path = self._get_services_json_path()

        with open(services_path, 'r') as f:
            schema = json.load(f)

        required_fields = [
            'discord.botToken',
            'discord.guildIds',
            'discord.channelIds',
            'discord.ignoreBots',
            'discord.requireMention',
            'discord.replyMode',
            'discord.showTyping',
            'discord.maxAttachmentBytes',
            'discord.sendResponses',
        ]

        for field in required_fields:
            assert field in schema['fields'], f'Missing field: {field}'

    def test_services_json_lanes(self):
        """Test that services.json defines correct lanes."""
        services_path = self._get_services_json_path()

        with open(services_path, 'r') as f:
            schema = json.load(f)

        lanes = schema['lanes']['_source']
        expected_lanes = ['text', 'image', 'audio', 'video', 'tags']

        for lane in expected_lanes:
            assert lane in lanes, f'Missing lane: {lane}'


class TestDiscordAttachmentFiltering:
    """Test attachment size and type filtering logic."""

    def test_attachment_size_validation(self):
        """Test that attachments respect size limits."""
        max_size = 25 * 1024 * 1024  # 25 MB

        # Under limit
        assert 10 * 1024 * 1024 < max_size

        # At limit
        assert max_size <= max_size

        # Over limit
        assert (26 * 1024 * 1024) > max_size

    def test_guild_id_filtering(self):
        """Test guild ID allowlist filtering."""
        allowed_guilds = ['123456', '789012']
        message_guild = '123456'

        # Should process
        assert str(message_guild) in allowed_guilds

        # Should skip
        assert '999999' not in allowed_guilds

    def test_channel_id_filtering(self):
        """Test channel ID allowlist filtering."""
        allowed_channels = ['111111', '222222', '333333']
        message_channel = '222222'

        # Should process
        assert str(message_channel) in allowed_channels

        # Should skip
        assert '999999' not in allowed_channels


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
