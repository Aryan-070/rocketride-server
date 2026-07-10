/**
 * MIT License
 *
 * Copyright (c) 2026 Aparavi Software AG
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

/**
 * Type definitions for chat application
 */

/**
 * Represents a single chat message in the conversation
 */
export interface Message {
	id: number;
	text: string;
	sender: 'user' | 'bot' | 'system' | 'status';
	timestamp: string;
	resultKey?: string | undefined;
	sseType?: string;
	// Inline media: when set, the message renders a player/viewer instead of
	// markdown. filePath is the logical FileStore path, pulled as chunks over
	// rrext_media. mediaUrl is a pre-resolved data URI (base64 fallback, nothing
	// to pull); mediaFallbackUrl is the signed URL, used only if the pull fails.
	filePath?: string | undefined;
	mediaUrl?: string | undefined;
	mediaFallbackUrl?: string | undefined;
	mediaMime?: string | undefined;
	mediaName?: string | undefined;
}

/**
 * Configuration for API connection mode
 */
export interface ChatConfig {
	devMode: boolean;
	host?: string;
	apiKey?: string;
}

/**
 * Connection state and control interface
 */
export interface ConnectionState {
	isConnected: boolean;
	connectionError: string | null;
	client: any | null;
	pipelineToken: string | null;
}
