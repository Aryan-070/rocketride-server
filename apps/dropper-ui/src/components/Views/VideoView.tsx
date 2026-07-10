/**
 * MIT License
 * Copyright (c) 2026 Aparavi Software AG
 * See LICENSE file for details.
 */

import React from 'react';
import { Video } from 'lucide-react';
import { ProcessedResults } from '../../types/dropper.types';

/**
 * Props for the VideoView component
 */
interface VideoViewProps {
	/** Array of video content groups to display */
	videos: ProcessedResults['videos'];
	/** Whether to display content in comparison mode (side-by-side) */
	compareMode: boolean;
	/** Callback to set element refs for scrolling functionality */
	setRef?: (filename: string, element: HTMLDivElement | null) => void;
}

/**
 * VideoView Component
 *
 * Plays video content produced by a pipeline. Each block holds one or more
 * URLs joined by '|||' (resolved via fsGetUrl, so streaming uses HTTP Range);
 * each renders as a native <video> player. No external player required.
 *
 * @param props - Component props
 * @returns React component displaying video content
 */
export const VideoView: React.FC<VideoViewProps> = ({ videos, compareMode, setRef }) => {
	// Show empty state if no videos are available
	if (videos.length === 0) {
		return (
			<div className="tab-content">
				<div className="no-content">
					<Video className="w-12 h-12 text-gray-300" />
					<p>No videos found in the processed files.</p>
				</div>
			</div>
		);
	}

	return (
		<div className="tab-content">
			<div className="content-list">
				{videos.map((group, groupIndex) => (
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
								{/* Show field name only when multiple video groups exist */}
								{group.contents.length > 1 && block.fieldName && (
									<div className="content-field-label">{block.fieldName}</div>
								)}
								<div className="content-item">
									<div className="media-grid">
										{/* Split videos by delimiter and render a player each */}
										{block.content.split('|||').map((videoUrl: string, vidIndex: number) => (
											<div key={vidIndex} className="media-wrapper">
												<video
													className="processed-video"
													src={videoUrl}
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
