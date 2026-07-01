// MIT License
//
// Copyright (c) 2026 Aparavi Software AG
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// =============================================================================
// useSubscriptions -- reads desktop/subscription state from AppRegistry
// =============================================================================

import { useMemo } from 'react';
import type { AppManifestEntry } from '../workspace/types';
import { useAppRegistry } from './AppRegistryContext';

// =============================================================================
// TYPES
// =============================================================================

/** App lifecycle status values computed server-side. */
export type AppStatus = 'auth' | 'free' | 'unsubscribed' | 'subscribed' | 'trialing' | 'past_due' | 'canceled';

/** @deprecated Use AppStatus instead. */
export type SubscriptionStatus = AppStatus;

// =============================================================================
// HOOK
// =============================================================================

/**
 * Returns the user's desktop apps from the app registry.
 *
 * Filters the registry to apps that have ``onDesktop`` set (i.e. apps
 * that arrived via the desktop fetch or desktop push events). Apps
 * registered only from the probe or catalog won't appear here.
 */
export function useSubscriptions(): {
	desktopApps: AppManifestEntry[];
	/** Quick lookup: is this appId on the desktop? */
	isOnDesktop: (appId: string) => boolean;
	/** Quick lookup: what's this app's appStatus? */
	getStatus: (appId: string) => AppStatus | undefined;
} {
	const { apps } = useAppRegistry();

	return useMemo(() => {
		// Build lookup maps from apps that have subscription data
		const statusMap = new Map<string, AppStatus>();
		const desktopSet = new Set<string>();
		const desktopApps: AppManifestEntry[] = [];

		for (const entry of apps) {
			if (!entry?.id) continue;
			// Only include apps with subscription/desktop metadata
			if (entry.appStatus) {
				statusMap.set(entry.id, entry.appStatus as AppStatus);
			}
			if (entry.onDesktop) {
				desktopSet.add(entry.id);
				desktopApps.push(entry);
			}
		}

		return {
			desktopApps,
			isOnDesktop: (appId: string) => desktopSet.has(appId),
			getStatus: (appId: string) => statusMap.get(appId),
		};
	}, [apps]);
}
