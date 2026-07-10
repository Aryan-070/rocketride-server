/**
 * MIT License
 * Copyright (c) 2026 Aparavi Software AG
 * See LICENSE file for details.
 */

import { UPLOAD_RESULT } from 'rocketride';
import { ProcessedResults, GroupedContent, ContentBlock } from '../types/dropper.types';

// ============================================================================
// TABLE PROCESSING
// ============================================================================

const normalizeTable = (tableText: string): string => {
	const lines = tableText.trim().split('\n');

	if (lines.length < 2) {
		return tableText;
	}

	const secondLine = lines[1];
	if (secondLine && secondLine.trim().match(/^\|[\s\-:]+\|/)) {
		return tableText;
	}

	const firstLine = lines[0];
	if (!firstLine) {
		return tableText;
	}

	const headerCols = (firstLine.match(/\|/g) || []).length - 1;
	const separator = '|' + Array(headerCols).fill('---').join('|') + '|';

	lines.splice(1, 0, separator);

	return lines.join('\n');
};

// ============================================================================
// CONTENT TYPE PROCESSORS
// ============================================================================

/**
 * Processes text content (simple strings only)
 */
const processTextData = (data: any): string[] => {
	const results: string[] = [];

	if (Array.isArray(data)) {
		const validItems = data.filter(item => typeof item === 'string' && item.trim());
		if (validItems.length > 0) {
			results.push(validItems.join('\n\n'));
		}
	} else if (typeof data === 'string' && data.trim()) {
		results.push(data);
	}

	return results;
};

/**
 * Processes object-based content (documents, questions, answers)
 * These are Doc objects, Question objects, or Answer objects
 * Returns them as-is without modification
 */
const processObjectData = (data: any): any[] => {
	const results: any[] = [];

	if (Array.isArray(data)) {
		data.forEach(item => {
			if (item !== null && item !== undefined) {
				results.push(item);
			}
		});
	} else if (data !== null && data !== undefined) {
		results.push(data);
	}

	return results;
};

/**
 * Processes table content
 */
const processTableData = (data: any): string[] => {
	const results: string[] = [];

	if (Array.isArray(data)) {
		const validItems = data.filter(item => typeof item === 'string' && item.trim());
		if (validItems.length > 0) {
			results.push(validItems.map(normalizeTable).join('\n\n'));
		}
	} else if (typeof data === 'string' && data.trim()) {
		results.push(normalizeTable(data));
	}

	return results;
};


/** A persisted media artifact named in the result: `{mime_type, path}`. */
export interface MediaArtifact {
	filename: string;
	kind: string;
	name: string;
	path: string;
	mime: string;
}

/** Data URLs for a lane's base64 entries, emitted when no FileStore persisted the bytes. */
const processMediaData = (fieldData: any, kind: string): string[] => {
	if (!Array.isArray(fieldData)) return [];
	return fieldData
		.filter(entry => entry && typeof entry === 'object' && typeof entry[kind] === 'string')
		.map(entry => `data:${entry.mime_type || 'application/octet-stream'};base64,${entry[kind]}`);
};

const MEDIA_LANES = new Set(['image', 'audio', 'video']);

/**
 * Every persisted media artifact named in the results.
 *
 * The response node announces each one over SSE, but that bus is lossy — a dropped
 * announcement would silently cost the user their media. The result always carries
 * the path, so the hook merges whatever SSE did not deliver.
 */
export const extractMediaArtifacts = (uploadResults: UPLOAD_RESULT[]): MediaArtifact[] => {
	const artifacts: MediaArtifact[] = [];
	for (const uploadResult of uploadResults) {
		const result: any = uploadResult.result;
		if (!result?.result_types) continue;
		for (const [fieldName, fieldType] of Object.entries(result.result_types)) {
			const kind = String(fieldType);
			if (!MEDIA_LANES.has(kind) || !Array.isArray(result[fieldName])) continue;
			for (const entry of result[fieldName]) {
				if (!entry || typeof entry.path !== 'string' || !entry.path) continue;
				artifacts.push({
					filename: uploadResult.filepath,
					kind,
					name: entry.path.split('/').pop() || kind,
					path: entry.path,
					mime: typeof entry.mime_type === 'string' ? entry.mime_type : ''
				});
			}
		}
	}
	return artifacts;
};

// ============================================================================
// GROUPING AND ORGANIZATION
// ============================================================================

/**
 * Groups content by filename, preserving field names
 * Supports both string content (text, tables, images) and object content (documents, questions, answers)
 */
const groupByFilename = (items: Array<{ filename: string; content: any; fieldName: string }>): GroupedContent[] => {
	const grouped = new Map<string, ContentBlock[]>();

	// Group items by filename
	items.forEach(({ filename, content, fieldName }) => {
		if (!grouped.has(filename)) {
			grouped.set(filename, []);
		}
		grouped.get(filename)!.push({ content, fieldName });
	});

	// Convert Map to array format
	return Array.from(grouped.entries()).map(([filename, contents]) => ({
		filename,
		contents
	}));
};

// ============================================================================
// MAIN PARSER
// ============================================================================

export const parseDropperResults = async (uploadResults: UPLOAD_RESULT[]): Promise<ProcessedResults> => {
	// Use 'any' for content type since it can be string or object
	const textItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const documentItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const tableItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const questionItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const answerItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const imageItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const audioItems: Array<{ filename: string; content: any; fieldName: string }> = [];
	const videoItems: Array<{ filename: string; content: any; fieldName: string }> = [];

	// Process each upload result
	for (const uploadResult of uploadResults) {
		const filename = uploadResult.filepath;
		const pipelineResult = uploadResult.result;

		// Skip results without proper structure
		if (!pipelineResult || !pipelineResult.result_types) {
			continue;
		}

		// Process each field based on its declared type
		for (const [fieldName, fieldType] of Object.entries(pipelineResult.result_types)) {
			const fieldData = pipelineResult[fieldName];

			switch (fieldType) {
				case 'text':
					// Process text content (simple strings)
					processTextData(fieldData).forEach(content => {
						textItems.push({ filename, content, fieldName });
					});
					break;

				case 'document':
				case 'documents':
					// Process document content (Doc objects)
					processObjectData(fieldData).forEach(content => {
						documentItems.push({ filename, content, fieldName });
					});
					break;

				case 'table':
				case 'tables':
					// Process and normalize table content (strings)
					processTableData(fieldData).forEach(content => {
						tableItems.push({ filename, content, fieldName });
					});
					break;

				// Persisted media (`path`) arrives live over SSE ('artifact_path') and is
				// merged in the hook; only the store-less base64 fallback is read here.
				case 'image':
				case 'images':
					processMediaData(fieldData, 'image').forEach(content => {
						imageItems.push({ filename, content, fieldName });
					});
					break;

				case 'audio':
				case 'audios':
					processMediaData(fieldData, 'audio').forEach(content => {
						audioItems.push({ filename, content, fieldName });
					});
					break;

				case 'video':
				case 'videos':
					processMediaData(fieldData, 'video').forEach(content => {
						videoItems.push({ filename, content, fieldName });
					});
					break;

				case 'question':
				case 'questions':
					// Process question content (Question objects)
					processObjectData(fieldData).forEach(content => {
						questionItems.push({ filename, content, fieldName });
					});
					break;

				case 'answer':
				case 'answers':
					// Process answer content (Answer objects - can be text, object, or array)
					processObjectData(fieldData).forEach(content => {
						answerItems.push({ filename, content, fieldName });
					});
					break;

				default:
					// Log unknown types for debugging
					console.warn('Unknown field type in pipeline result:', fieldType);
			}
		}
	}

	// Group content by filename and return organized structure
	return {
		rawJson: uploadResults,
		textContent: groupByFilename(textItems),
		documents: groupByFilename(documentItems),
		tables: groupByFilename(tableItems),
		images: groupByFilename(imageItems),
		videos: groupByFilename(videoItems),
		audios: groupByFilename(audioItems),
		questions: groupByFilename(questionItems),
		answers: groupByFilename(answerItems)
	};
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

export const generateFileId = (): string => {
	return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
};

export const formatBytes = (bytes: number): string => {
	if (bytes === 0) return '0 B';

	const k = 1024;
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];

	const i = Math.floor(Math.log(bytes) / Math.log(k));

	return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};