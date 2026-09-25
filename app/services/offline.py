"""Helpers for proving that the application can run without the internet."""
from pathlib import Path
import re


EXTERNAL_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
LOCAL_DATABASE_PREFIX = "sqlite://"


def database_is_local(database_uri):
    """Return True when SQLAlchemy is using SQLite on this machine."""
    return str(database_uri).startswith(LOCAL_DATABASE_PREFIX)


def database_persists(database_uri):
    """Return True when SQLite is backed by a file rather than memory."""
    uri = str(database_uri)
    return uri.startswith("sqlite:///") and not uri.endswith(":memory:")


def external_runtime_references(app):
    """List runtime resource files that contain absolute HTTP(S) URLs."""
    roots = [Path(app.template_folder), Path(app.static_folder)]
    findings = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".html", ".css", ".js"}:
                continue
            text = path.read_text(encoding="utf-8")
            if EXTERNAL_URL_PATTERN.search(text):
                findings.append(str(path.relative_to(path.parents[1])))
    return findings


def offline_report(app):
    """Return the facts shown to the operator on the offline status page."""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    external_references = external_runtime_references(app)
    local_database = database_is_local(uri)
    persistent_database = database_persists(uri)
    return {
        "ok": local_database and persistent_database and not external_references,
        "database_engine": "SQLite",
        "database_uri": uri,
        "local_database": local_database,
        "persistent_database": persistent_database,
        "external_references": external_references,
    }
