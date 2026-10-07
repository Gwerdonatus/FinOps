from django.http import HttpRequest

from .models import Membership

SESSION_KEY = "active_workspace_id"


class ActiveWorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.workspace = None
        request.workspace_role = None

        if request.user.is_authenticated:
            ws_id = request.session.get(SESSION_KEY)

            membership_qs = Membership.objects.select_related("workspace").filter(user=request.user)

            # If no membership, allow user to login but they won't see app pages properly.
            if membership_qs.exists():
                if ws_id:
                    membership = membership_qs.filter(workspace_id=ws_id).first()
                else:
                    membership = None

                if membership is None:
                    membership = membership_qs.first()
                    request.session[SESSION_KEY] = membership.workspace_id

                request.workspace = membership.workspace
                request.workspace_role = membership.role

        response = self.get_response(request)
        return response
