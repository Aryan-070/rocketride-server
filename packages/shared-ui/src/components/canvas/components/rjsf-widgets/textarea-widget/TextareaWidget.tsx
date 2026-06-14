/**
 * MIT License
 * Copyright (c) 2026 Aparavi Software AG
 * See LICENSE file for details.
 */

import { ChangeEvent, FocusEvent, useState, useEffect, useCallback, useRef, KeyboardEvent, FC } from 'react';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import { WidgetProps } from '@rjsf/utils';

import { useEnvVarAutocomplete } from '../hooks/useEnvVarAutocomplete';
import EnvVarSuggestions from '../env-var-suggestions/EnvVarSuggestions';

// =============================================================================
// Component
// =============================================================================

const TextareaWidget: FC<WidgetProps> = ({ id, value, label, required, autofocus, disabled, readonly, rawErrors, onChange, onBlur, onFocus, options, schema, formContext }) => {
	const [controlledValue, setControlledValue] = useState(value ?? '');

	useEffect(() => {
		if (value !== undefined && value !== null) {
			setControlledValue(value);
		}
	}, [value]);

	const minRows = (options?.rows as number) ?? 1;
	const maxRows = (options?.maxRows as number) ?? 5;

	// --- Env var autocomplete ------------------------------------------------
	const inputRef = useRef<HTMLTextAreaElement>(null);
	const envKeys: string[] = Array.isArray(formContext?.envKeys) ? formContext.envKeys : [];
	const autocomplete = useEnvVarAutocomplete(envKeys);

	const onEnvVarSelect = useCallback(
		(key: string) => {
			const newValue = autocomplete.handleSelect(key, String(controlledValue ?? ''), inputRef.current);
			setControlledValue(newValue);
			onChange(newValue === '' ? options.emptyValue : newValue);
		},
		[autocomplete, controlledValue, onChange, options.emptyValue],
	);

	// Open the full variable list from the picker button (no `${` typing needed).
	const handleOpenPicker = useCallback(() => {
		const el = inputRef.current;
		if (!el) return;
		el.focus();
		autocomplete.openAll(el, el.selectionStart ?? String(controlledValue ?? '').length);
	}, [autocomplete, controlledValue]);

	const showVarPicker = envKeys.length > 0 && !disabled && !readonly;

	const handleKeyDown = useCallback(
		(e: KeyboardEvent<HTMLTextAreaElement>) => {
			if (!autocomplete.isOpen) return;
			if (e.key === 'ArrowDown') {
				e.preventDefault();
				autocomplete.moveHighlight('down');
			} else if (e.key === 'ArrowUp') {
				e.preventDefault();
				autocomplete.moveHighlight('up');
			} else if (e.key === 'Enter') {
				e.preventDefault();
				if (autocomplete.suggestions[autocomplete.highlightedIndex]) {
					onEnvVarSelect(autocomplete.suggestions[autocomplete.highlightedIndex]);
				}
			} else if (e.key === 'Escape') {
				autocomplete.handleDismiss();
			}
		},
		[autocomplete, onEnvVarSelect],
	);

	return (
		<>
			<TextField
				id={id}
				name={id}
				required={required}
				label={label}
				size="small"
				fullWidth
				multiline
				minRows={minRows}
				maxRows={maxRows}
				value={controlledValue}
				onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
					const val = e.target.value;
					const cursor = e.target.selectionStart ?? val.length;
					setControlledValue(val);
					onChange(val === '' ? options.emptyValue : val);
					autocomplete.handleInputChange(val, cursor, e.target);
				}}
				onBlur={(e: FocusEvent<HTMLTextAreaElement>) => onBlur && onBlur(id, e.target.value)}
				onFocus={(e: FocusEvent<HTMLTextAreaElement>) => onFocus && onFocus(id, e.target.value)}
				onKeyDown={handleKeyDown}
				inputRef={inputRef}
				autoFocus={autofocus}
				disabled={disabled || readonly}
				error={!!rawErrors?.length}
				variant="outlined"
				InputProps={
					showVarPicker
						? {
								endAdornment: (
									<InputAdornment position="end" sx={{ alignItems: 'flex-start', mt: 1 }}>
										<IconButton
											size="small"
											edge="end"
											tabIndex={-1}
											aria-label="Insert variable"
											title="Insert variable"
											onClick={handleOpenPicker}
											sx={{ fontSize: 13, fontFamily: 'var(--rr-font-family-widget, monospace)', color: 'var(--rr-text-secondary)', px: 0.5 }}
										>
											{'${}'}
										</IconButton>
									</InputAdornment>
								),
							}
						: undefined
				}
				InputLabelProps={{ shrink: true }}
				helperText={typeof options?.description === 'string' ? options.description : schema?.description}
			/>
			{envKeys.length > 0 && (
				<EnvVarSuggestions open={autocomplete.isOpen} anchorEl={autocomplete.anchorEl} suggestions={autocomplete.suggestions} highlightedIndex={autocomplete.highlightedIndex} onSelect={onEnvVarSelect} onDismiss={autocomplete.handleDismiss} />
			)}
		</>
	);
};

export default TextareaWidget;
