from __future__ import annotations

import logging
import os

from src.database.connection import init_db
from src.ui.app import CSS, build_app, build_theme
from src.utils.logging_config import configure_logging


def main() -> None:
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    configure_logging()
    init_db()
    from src.agents.transcription import _get_whisper_model
    from src.graph.workflow import graph

    logging.info("Workflow initialized (%s nodes)", len(graph.nodes), extra={"node": "startup"})
    if os.getenv("WHISPER_PRELOAD", "true").lower() == "true":
        _get_whisper_model()
    build_app().queue().launch(
        server_name="0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1",
        server_port=7860,
        show_error=False,
        theme=build_theme(),
        css=CSS,
        max_file_size="50mb",
        footer_links=[],
    )


if __name__ == "__main__":
    main()
