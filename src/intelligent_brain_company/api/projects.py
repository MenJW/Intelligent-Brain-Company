from __future__ import annotations

from flask import current_app, jsonify, request

from intelligent_brain_company.api import projects_bp
from intelligent_brain_company.domain.models import IdeaBrief
from intelligent_brain_company.domain.project_state import ProjectRecord


SUPPORTED_CONVERSATION_LANGUAGES = {"zh-CN", "en-US"}


def _normalize_conversation_language(language: str | None) -> str:
    if not language:
        return "zh-CN"
    value = str(language).strip()
    return value if value in SUPPORTED_CONVERSATION_LANGUAGES else "zh-CN"


@projects_bp.route("/api/projects", methods=["GET"])
def list_projects():
    store = current_app.extensions["project_store"]
    items = [project.to_dict() for project in store.list_projects()]
    return jsonify({"success": True, "data": items})


@projects_bp.route("/api/projects", methods=["POST"])
def create_project():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "title is required"}), 400

    brief = IdeaBrief(
        title=title,
        summary=payload.get("summary", ""),
        user_constraints=payload.get("constraints", []),
        success_metrics=payload.get("metrics", []),
    )
    project = ProjectRecord.create(name=payload.get("name") or title, idea=brief)
    project.conversation_language = _normalize_conversation_language(payload.get("language"))
    store = current_app.extensions["project_store"]
    store.save_project(project)
    return jsonify({"success": True, "data": project.to_dict()}), 201


@projects_bp.route("/api/projects/<project_id>", methods=["GET"])
def get_project(project_id: str):
    store = current_app.extensions["project_store"]
    project = store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404
    return jsonify({"success": True, "data": project.to_dict()})


@projects_bp.route("/api/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id: str):
    store = current_app.extensions["project_store"]
    deleted = store.delete_project(project_id)
    if not deleted:
        return jsonify({"success": False, "error": "project not found"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id}})


@projects_bp.route("/api/projects/<project_id>/language", methods=["POST"])
def update_project_language(project_id: str):
    payload = request.get_json(silent=True) or {}
    language = _normalize_conversation_language(payload.get("language"))

    store = current_app.extensions["project_store"]
    project = store.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": "project not found"}), 404

    project.conversation_language = language
    project.touch()
    store.save_project(project)
    return jsonify(
        {
            "success": True,
            "data": {
                "project_id": project.project_id,
                "language": project.conversation_language,
            },
        }
    )