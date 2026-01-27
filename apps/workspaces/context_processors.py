def workspace_context(request):
    return {
        "active_workspace": getattr(request, "workspace", None),
        "workspace_role": getattr(request, "workspace_role", None),
    }
