// =============================================================================
// MIT License
// Copyright (c) 2026 Aparavi Software AG
// =============================================================================

/**
 * Shared handler for checkout action-plan (Free / Enterprise) button clicks.
 *
 * The checkout modal's action buttons cannot open links themselves inside the
 * VS Code webview sandbox (window.open / window.location are blocked), so every
 * host webview (Project, Account, Settings) forwards the click here via a
 * ``checkout:action`` message.
 */

import * as vscode from 'vscode';

/**
 * Routes a checkout action-plan button click to the appropriate native action.
 *
 * @param actionType - The plan action type: 'mailto' (Enterprise "Contact us")
 *                     opens an email draft; anything else (Free "Get started",
 *                     a 'link') opens Settings on Development Mode, forcing Local.
 */
export function openCheckoutAction(actionType?: string): void {
	if (actionType === 'mailto') {
		vscode.env.openExternal(vscode.Uri.parse('mailto:sales@rocketride.ai'));
	} else {
		vscode.commands.executeCommand('rocketride.page.settings.open', 'development', undefined, 'local');
	}
}
