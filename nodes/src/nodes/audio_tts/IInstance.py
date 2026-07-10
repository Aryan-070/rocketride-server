# =============================================================================
# MIT License
# Copyright (c) 2026 Aparavi Software AG
# =============================================================================

from rocketlib import IInstanceBase, AVI_ACTION, warning
from .IGlobal import IGlobal, MP3_MIME


class IInstance(IInstanceBase):
    IGlobal: IGlobal

    def writeDocuments(self, documents):
        docs = documents if isinstance(documents, list) else [documents]
        text = '\n'.join(
            doc.page_content for doc in docs if doc.page_content and doc.type not in ('Image', 'Audio', 'Video')
        )
        self.writeText(text)

    def writeQuestions(self, question):
        text = ' '.join(q.text for q in question.questions) if question.questions else ''
        self.writeText(text)

    def writeAnswers(self, answer):
        text = answer.getText() if hasattr(answer, 'getText') else str(answer)
        self.writeText(text)

    def writeText(self, text: str):
        """Synthesise ``text`` and emit it as it is produced, one MP3 frame at a time.

        BEGIN goes out before the model has run, so a consumer can open the artifact
        and start reading; each frame follows as the encoder produces it. END always
        fires, even on failure, so the downstream stream is never left open.
        """
        value = (text or '').strip()
        if not value:
            return

        self.instance.writeAudio(AVI_ACTION.BEGIN, MP3_MIME)
        try:
            for frames in self.IGlobal.synthesize_stream(value):
                self.instance.writeAudio(AVI_ACTION.WRITE, MP3_MIME, frames)
        except Exception as e:
            warning(f'TTS synthesis failed: {e}')
            raise
        finally:
            self.instance.writeAudio(AVI_ACTION.END, MP3_MIME)
