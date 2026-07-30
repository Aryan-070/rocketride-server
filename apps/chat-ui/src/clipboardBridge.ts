/**
 * MIT License
 *
 * Copyright (c) 2026 Aparavi Software AG
 */

export interface ClipboardTextControl {
	tagName: string;
	value: string;
	selectionStart: number | null;
	selectionEnd: number | null;
	setSelectionRange(start: number, end: number): void;
}

export type ChatSelectionTarget = 'editable' | 'transcript' | 'none';
export type EmbeddedClipboardCommand = 'copy' | 'cut' | 'paste' | 'selectAll';

export interface EmbeddedClipboardKeyboardEvent {
	key: string;
	metaKey: boolean;
	ctrlKey: boolean;
	altKey?: boolean;
}

export function isVSCodeEmbeddedChat(search: string): boolean {
	return new URLSearchParams(search).get('_rocketrideHost') === 'vscode';
}

export function getEmbeddedClipboardCommand(
	event: EmbeddedClipboardKeyboardEvent
): EmbeddedClipboardCommand | undefined {
	if ((!event.metaKey && !event.ctrlKey) || event.altKey) return undefined;

	switch (event.key.toLowerCase()) {
		case 'a':
			return 'selectAll';
		case 'c':
			return 'copy';
		case 'v':
			return 'paste';
		case 'x':
			return 'cut';
		default:
			return undefined;
	}
}

export async function copyChatText(
	text: string,
	isEmbedded: boolean,
	postMessage: (message: unknown) => void,
	writeText: (text: string) => Promise<void>
): Promise<void> {
	if (isEmbedded) {
		postMessage({ type: 'copyText', text });
		return;
	}

	await writeText(text);
}

export function isClipboardTextControl(element: unknown): element is ClipboardTextControl {
	if (!element || typeof element !== 'object') return false;

	const candidate = element as Partial<ClipboardTextControl>;
	return (
		(candidate.tagName === 'INPUT' || candidate.tagName === 'TEXTAREA') &&
		typeof candidate.value === 'string' &&
		typeof candidate.setSelectionRange === 'function'
	);
}

export function isActiveClipboardTextControl(
	activeElement: unknown,
	textControl: unknown
): textControl is ClipboardTextControl {
	return activeElement === textControl && isClipboardTextControl(textControl);
}

function clampSelection(value: string, start: number | null, end: number | null): [number, number] {
	const safeStart = Math.max(0, Math.min(value.length, start ?? value.length));
	const safeEnd = Math.max(safeStart, Math.min(value.length, end ?? safeStart));
	return [safeStart, safeEnd];
}

export function getSelectedClipboardText(activeElement: unknown, documentSelection: string): string {
	if (!isClipboardTextControl(activeElement)) return documentSelection;

	const [start, end] = clampSelection(activeElement.value, activeElement.selectionStart, activeElement.selectionEnd);
	return activeElement.value.slice(start, end);
}

export function selectAllChatContent(
	activeElement: unknown,
	selectTranscript: () => boolean
): ChatSelectionTarget {
	if (isClipboardTextControl(activeElement)) {
		activeElement.setSelectionRange(0, activeElement.value.length);
		return 'editable';
	}

	return selectTranscript() ? 'transcript' : 'none';
}

export function insertClipboardText(
	value: string,
	selectionStart: number | null,
	selectionEnd: number | null,
	text: string
): { value: string; caret: number } {
	const [start, end] = clampSelection(value, selectionStart, selectionEnd);
	return {
		value: value.slice(0, start) + text + value.slice(end),
		caret: start + text.length,
	};
}

export function cutClipboardText(
	value: string,
	selectionStart: number | null,
	selectionEnd: number | null
): { value: string; text: string; caret: number } {
	const [start, end] = clampSelection(value, selectionStart, selectionEnd);
	return {
		value: value.slice(0, start) + value.slice(end),
		text: value.slice(start, end),
		caret: start,
	};
}
