/**
 * MIT License
 * Copyright (c) 2026 Aparavi Software AG
 * See LICENSE file for details.
 */

import React from 'react';
import { Music } from 'lucide-react';
import { ProcessedResults } from '../../types/dropper.types';

/**
 * Props for the AudioView component
 */
interface AudioViewProps {
	/** Array of audio content groups to display */
	audios: ProcessedResults['audios'];
	/** Whether to display content in comparison mode (side-by-side) */
	compareMode: boolean;
	/** Callback to set element refs for scrolling functionality */
	setRef?: (filename: string, element: HTMLDivElement | null) => void;
}

/**
 * AudioView Component
 *
 * Plays audio content produced by a pipeline. Each block holds one or more
 * URLs joined by '|||' (resolved via fsGetUrl, streamed over HTTP Range); each
 * renders as a native <audio> player. No external player required.
 *
 * @param props - Component props
 * @returns React component displaying audio content
 */
export const AudioView: React.FC<AudioViewProps> = ({ audios, compareMode, setRef }) => {
	// Show empty state if no audios are available
	if (audios.length === 0) {
		return (
			<div className="tab-content">
				<div className="no-content">
					<Music className="w-12 h-12 text-gray-300" />
					<p>No audio found in the processed files.</p>
				</div>
			</div>
		);
	}

	return (
		<div className="tab-content">
			<div className="content-list">
				{audios.map((group, groupIndex) => (
					<div
						key={groupIndex}
						ref={(el) => {
							if (el && setRef) setRef(group.filename, el);
						}}
					>
						{/* File header */}
						<div className="content-item-header">{group.filename}</div>

						{group.contents.map((block: any, contentIndex: number) => (
							<div key={contentIndex} className={compareMode ? 'compare-column' : 'content-item-wrapper'}>
								{/* Show field name only when multiple audio groups exist */}
								{group.contents.length > 1 && block.fieldName && (
									<div className="content-field-label">{block.fieldName}</div>
								)}
								<div className="content-item">
									<div className="media-grid">
										{/* Split audios by delimiter and render a player each */}
										{block.content.split('|||').map((audioUrl: string, audIndex: number) => (
											<div key={audIndex} className="media-wrapper">
												<audio
													className="processed-audio"
													src={audioUrl}
													controls
													preload="metadata"
												/>
											</div>
										))}
									</div>
								</div>
							</div>
						))}
					</div>
				))}
			</div>
		</div>
	);
};
