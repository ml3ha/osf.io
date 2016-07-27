from django.conf.urls import url

from . import views

urlpatterns = [
    # /v2/preprints/
    url(r'^$', views.PreprintList.as_view(), name=views.PreprintList.view_name),
    # /v2/preprints/<preprint_id>/
    url(r'^(?P<node_id>\w+)/$', views.PreprintDetail.as_view(), name=views.PreprintDetail.view_name),
    #/v2/preprints/<preprint_id>/authors/
    url(r'^(?P<node_id>\w+)/authors', views.PreprintAuthorsList.as_view(), name=views.PreprintAuthorsList.view_name),

]

# Routes only active in local/staging environments
#if settings.DEV_MODE:
#    urlpatterns.extend([
#        # Custom citations
#        url(r'^(?P<node_id>\w+)/citations/$', views.NodeAlternativeCitationsList.as_view(), name=views.NodeAlternativeCitationsList.view_name),
#        url(r'^(?P<node_id>\w+)/citations/(?P<citation_id>\w+)/$', views.NodeAlternativeCitationDetail.as_view(), name=views.NodeAlternativeCitationDetail.view_name),
#    ])
