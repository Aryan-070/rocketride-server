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

import React, { useEffect, useState } from 'react';
import { getClient } from '../hooks/clientSingleton';
import { getMediaInfo, FileCategory } from '../utils/mediaTypes';
import { MarkdownRenderer } from './MarkdownRenderer';

interface InlineMediaRendererProps {
	/** Logical FileStore path; the bytes are pulled as chunks over rrext_media. */
	path?: string | undefined;
	/** Pre-resolved data URI (base64 fallback — there is nothing to pull). */
	directUrl?: string | undefined;
	/** Signed URL from the announcement, used only if the chunk pull fails. */
	fallbackUrl?: string | undefined;
	/** MIME type — used to classify when only a directUrl is available. */
	mime?: string | undefined;
	/** File name shown as caption/download label. */
	name?: string | undefined;
	/** Optional hook to open the file in the File Explorer (capability layer). */
	onOpenInExplorer?: ((path: string) => void) | undefined;
}

type Source =
	| { kind: 'loading' }
	| { kind: 'error'; message: string }
	| { kind: 'url'; url: string }
	| { kind: 'blob'; url: string }
	| { kind: 'text'; text: string };

/** Coarse category from a MIME type, for the directUrl (base64) path. */
function categoryFromMime(mime?: string): FileCategory {
	if (!mime) return 'binary';
	if (mime.startsWith('video/')) return 'video';
	if (mime.startsWith('audio/')) return 'audio';
	if (mime.startsWith('image/')) return 'image';
	if (mime === 'application/pdf') return 'pdf';
	return 'binary';
}

/**
 * Renders a pipeline-produced media file inline in the chat, mirroring the File
 * Explorer (getMediaInfo + contentMode). Resolves a fresh signed URL on mount so
 * an expired token never leaves a dead link; falls back to a pre-resolved
 * directUrl (base64) when the pipeline could not persist to the FileStore.
 */
export const InlineMediaRenderer: React.FC<InlineMediaRendererProps> = ({ path, directUrl, fallbackUrl, mime, name, onOpenInExplorer }) => {
	// When we only have a directUrl, classify by MIME; otherwise by path.
	const info = path ? getMediaInfo(path) : { category: categoryFromMime(mime), mime: mime ?? '', contentMode: 'link' as const };
	const category = info.category;
	const contentMode = info.contentMode;
	const label = name ?? (path ? path.split('/').pop() : undefined) ?? 'file';
	const [source, setSource] = useState<Source>(directUrl ? { kind: 'url', url: directUrl } : { kind: 'loading' });

	useEffect(() => {
		if (directUrl) {
			setSource({ kind: 'url', url: directUrl });
			return;
		}
		if (!path) return;
		let cancelled = false;
		let objectUrl: string | null = null;
		const client = getClient();
		if (!client) {
			setSource({ kind: 'error', message: 'Not connected — cannot load file.' });
			return;
		}
		const fail = (e: unknown) => {
			if (!cancelled) setSource({ kind: 'error', message: e instanceof Error ? e.message : 'Failed to load file.' });
		};

		// Text-ish modes render decoded text; link/blob modes render bytes.
		const wantsText = contentMode !== 'link' && contentMode !== 'blob';

		// Primary: pull the bytes over the DAP channel (rrext_media), which needs only
		// task.data. For media this returns at once with a MediaSource url, so playback
		// starts on the first chunk while the producing node is still writing.
		const pullViaMedia = async () => {
			if (wantsText) {
				const blob = await client.mediaFetchBlob(path, mime);
				if (cancelled) return;
				const text = await blob.text();
				if (!cancelled) setSource({ kind: 'text', text });
				return;
			}
			objectUrl = await client.mediaPlaybackUrl(path, mime);
			if (cancelled) return;
			setSource({ kind: 'blob', url: objectUrl });
		};

		// Fallback: signed-URL path, for when the chunk pull fails (an older server
		// without rrext_media, or a revoked handle). Prefers the URL the server
		// already signed into the announcement; fsGetUrl needs task.store.
		const pullViaUrl = async () => {
			if (wantsText) {
				const text = await client.fsReadString(path);
				if (!cancelled) setSource({ kind: 'text', text });
				return;
			}
			const url = fallbackUrl ?? (await client.fsGetUrl(path));
			if (contentMode === 'link') {
				if (!cancelled) setSource({ kind: 'url', url });
			} else {
				const resp = await fetch(url);
				if (!resp.ok) throw new Error(`Fetch failed (${resp.status})`);
				const blob = await resp.blob();
				objectUrl = URL.createObjectURL(blob);
				if (!cancelled) setSource({ kind: 'blob', url: objectUrl });
			}
		};

		pullViaMedia().catch(() => pullViaUrl().catch(fail));

		return () => {
			cancelled = true;
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [path, directUrl, fallbackUrl, contentMode, mime]);

	const explorerButton = onOpenInExplorer && path ? (
		<button className="inline-media-open" onClick={() => onOpenInExplorer(path)}>
			Open in File Explorer
		</button>
	) : null;

	if (source.kind === 'loading') {
		return (
			<div className="inline-media inline-media-loading">
				<span className="inline-media-name">{label}</span>
				<span className="inline-media-spinner" />
			</div>
		);
	}

	if (source.kind === 'error') {
		return (
			<div className="inline-media inline-media-error">
				<span className="inline-media-name">{label}</span>
				<span className="inline-media-errortext">{source.message}</span>
				{explorerButton}
			</div>
		);
	}

	const url = source.kind === 'url' || source.kind === 'blob' ? source.url : undefined;
	let body: React.ReactNode;
	if (category === 'video' && url) {
		body = <video className="inline-media-video" src={url} controls preload="metadata" />;
	} else if (category === 'audio' && url) {
		body = <audio className="inline-media-audio" src={url} controls preload="metadata" />;
	} else if (category === 'image' && url) {
		body = <img className="inline-media-image" src={url} alt={label} />;
	} else if (category === 'pdf' && url) {
		body = <iframe className="inline-media-pdf" src={url} title={label} />;
	} else if (category === 'markdown' && source.kind === 'text') {
		body = <MarkdownRenderer content={source.text} />;
	} else if ((category === 'json' || category === 'code' || category === 'text') && source.kind === 'text') {
		body = <pre className="inline-media-text">{source.text}</pre>;
	} else {
		body = (
			<a className="inline-media-download" href={url} target="_blank" rel="noopener noreferrer">
				Download {label}
			</a>
		);
	}

	return (
		<div className={`inline-media inline-media-${category}`}>
			{body}
			<div className="inline-media-footer">
				<span className="inline-media-name">{label}</span>
				{explorerButton}
			</div>
		</div>
	);
};
