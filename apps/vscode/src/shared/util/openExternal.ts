// =============================================================================
// MIT License
// Copyright (c) 2026 Aparavi Software AG
// =============================================================================

import * as vscode from 'vscode';
import { getLogger } from './output';

/**
 * URI schemes a webview is allowed to open through the host. The webview is a
 * lower-trust boundary and vscode.env.openExternal hands ANY scheme to the OS
 * (file:, custom app URIs, ...), so we restrict to the schemes our CTAs use:
 * https links and mailto.
 */
const ALLOWED_SCHEMES = new Set(['https', 'mailto']);

/**
 * Opens a webview-supplied URL via the VS Code shell after allowlisting its
 * scheme. Unparseable or disallowed URLs are dropped (and logged), never opened.
 *
 * @param rawUrl - The URL posted by the webview (e.g. a plan action href).
 */
export async function openExternalUrl(rawUrl: string): Promise<void> {
	let uri: vscode.Uri;
	try {
		// strict=true rejects malformed input instead of coercing it.
		uri = vscode.Uri.parse(rawUrl, true);
	} catch {
		getLogger().info(`[openExternalUrl] ignored unparseable url: ${rawUrl}`);
		return;
	}

	if (!ALLOWED_SCHEMES.has(uri.scheme)) {
		getLogger().info(`[openExternalUrl] blocked disallowed scheme '${uri.scheme}'`);
		return;
	}

	await vscode.env.openExternal(uri);
}
