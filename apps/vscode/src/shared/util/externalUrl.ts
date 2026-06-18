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
 * Opens an external URL in the user's browser/mail client via the extension
 * host, gated behind the {@link isAllowedExternalUrl} (https/http/mailto)
 * allowlist. This is the single place webview ``openExternal`` messages are
 * funnelled through, so the scheme allowlist lives only here.
 *
 * @param url - The URL to open (from a webview message).
 * @param onReject - Optional callback invoked with a human-readable reason when
 *   `url` is present but its scheme is not allowlisted. Hosts use this to log or
 *   surface an error; when omitted the rejection is silently ignored.
 * @returns A promise that resolves once the URL has been opened (or rejected).
 */
export async function openExternalUrl(url: string, onReject?: (msg: string) => void): Promise<void> {
	if (isAllowedExternalUrl(url)) {
		await vscode.env.openExternal(vscode.Uri.parse(url));
	} else {
		onReject?.(`Refused to open external URL with unsupported scheme: ${url}`);
	}
}
