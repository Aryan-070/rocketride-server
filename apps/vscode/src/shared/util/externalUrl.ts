import * as vscode from 'vscode';

/** True when `raw` parses to an allowlisted external scheme (https/http/mailto). */
export function isAllowedExternalUrl(raw: string): boolean {
	try {
		const scheme = vscode.Uri.parse(raw).scheme.toLowerCase();
		return scheme === 'https' || scheme === 'http' || scheme === 'mailto';
	} catch {
		return false;
	}
}

/**
 * Opens an external URL via the VS Code host (`vscode.env.openExternal`).
 *
 * The scheme allowlist (https/http/mailto) lives here so every webview host
 * routes external links — e.g. the checkout "Contact us" CTA — through a single
 * hardened code path. Webviews are sandboxed: window.open / window.location open
 * a blank page and trap the view, so external links must go through the host.
 *
 * @param url      - The URL to open. Must use an allowlisted scheme.
 * @param onReject - Optional callback invoked with a message when `url` uses a
 *                   disallowed scheme. Defaults to a console warning.
 * @example
 *   await openExternalUrl('mailto:sales@example.com', (msg) => logger.error(msg));
 */
export async function openExternalUrl(url: string, onReject?: (message: string) => void): Promise<void> {
	if (!url) return;
	if (!isAllowedExternalUrl(url)) {
		const message = `Blocked unsupported external URL scheme: ${url}`;
		if (onReject) {
			onReject(message);
		} else {
			console.warn(`[openExternalUrl] ${message}`);
		}
		return;
	}
	await vscode.env.openExternal(vscode.Uri.parse(url));
}
