# -*- coding: utf-8 -*-
import collections
import httplib as http

from framework import request
from framework.exceptions import HTTPError
from framework.auth.decorators import must_be_logged_in
from framework.forms.utils import sanitize
from framework.auth.core import get_current_user

from website import settings
from website.filters import gravatar
from website.models import Guid, Comment
from website.project.decorators import must_be_contributor_or_public
from datetime import datetime
from website.project.model import has_anonymous_link



def resolve_target(node, guid):

    if not guid:
        return node
    target = Guid.load(guid)
    if target is None:
        raise HTTPError(http.BAD_REQUEST)
    return target.referent


def collect_discussion(target, users=None):

    users = users or collections.defaultdict(list)
    for comment in getattr(target, 'commented', []):
        if not comment.is_deleted:
            users[comment.user].append(comment)
        collect_discussion(comment, users=users)
    return users


@must_be_contributor_or_public
def comment_discussion(**kwargs):

    node = kwargs['node'] or kwargs['project']
    auth = kwargs['auth']
    users = collect_discussion(node)
    view_only_link = auth.private_key or request.args.get('view_only', '').strip('/')
    anonymous = has_anonymous_link(node, view_only_link) if view_only_link else False
    # Sort users by comment frequency
    # TODO: Allow sorting by recency, combination of frequency and recency
    sorted_users = sorted(
        users.keys(),
        key=lambda item: len(users[item]),
        reverse=True,
    )

    return {
        'discussion': [
            {
                'id': user._id if not anonymous else '',
                'url': user.url if not anonymous else '',
                'fullname': user.fullname if not anonymous else '',
                'isContributor': node.is_contributor(user),
                'gravatarUrl': gravatar(
                    user, use_ssl=True,
                    size=settings.GRAVATAR_SIZE_DISCUSSION,

                )if not anonymous else '',


            }
            for user in sorted_users
        ]
    }


def serialize_comment(comment, auth, anonymous=False):
    return {
        'id': comment._id,
        'author': {
            'id': comment.user._id if not anonymous else '',
            'url': comment.user.url if not anonymous else '',
            'name': comment.user.fullname if not anonymous else 'A user',
            'gravatarUrl': gravatar(
                    comment.user, use_ssl=True,
                    size=settings.GRAVATAR_SIZE_DISCUSSION) if not anonymous else '',
        },
        'dateCreated': comment.date_created.strftime('%m/%d/%y %H:%M:%S'),
        'dateModified': comment.date_modified.strftime('%m/%d/%y %H:%M:%S'),
        'content': comment.content,
        'hasChildren': bool(getattr(comment, 'commented', [])),
        'canEdit': comment.user == auth.user ,
        'modified': comment.modified,
        'isDeleted': comment.is_deleted,
        'isAbuse': auth.user and auth.user._id in comment.reports,
    }


def serialize_comments(record, auth, anonymous=False):

    return [
        serialize_comment(comment, auth, anonymous)
        for comment in getattr(record, 'commented', [])
    ]


def kwargs_to_comment(kwargs, owner=False):

    comment = Comment.load(kwargs.get('cid'))
    if comment is None:
        raise HTTPError(http.BAD_REQUEST)

    if owner:
        auth = kwargs['auth']
        if auth.user != comment.user:
            raise HTTPError(http.FORBIDDEN)

    return comment


@must_be_logged_in
@must_be_contributor_or_public
def add_comment(**kwargs):

    auth = kwargs['auth']
    node = kwargs['node'] or kwargs['project']

    if not node.comment_level:
        raise HTTPError(http.BAD_REQUEST)

    if not node.can_comment(auth):
        raise HTTPError(http.FORBIDDEN)

    guid = request.json.get('target')
    target = resolve_target(node, guid)

    content = request.json.get('content').strip()
    content = sanitize(content)
    if not content:
        raise HTTPError(http.BAD_REQUEST)
    if len(content) > settings.COMMENT_MAXLENGTH:
        raise HTTPError(http.BAD_REQUEST)

    comment = Comment.create(
        auth=auth,
        node=node,
        target=target,
        user=auth.user,
        content=content,
    )
    comment.save()

    return {
        'comment': serialize_comment(comment, auth)
   }, http.CREATED


@must_be_contributor_or_public
def list_comments(**kwargs):
    auth = kwargs['auth']
    node = kwargs['node'] or kwargs['project']
    view_only_link = auth.private_key or request.args.get('view_only', '').strip('/')
    anonymous = has_anonymous_link(node, view_only_link) if view_only_link else False
    guid = request.args.get('target')
    target = resolve_target(node, guid)
    user = get_current_user()
    comments = serialize_comments(target, auth, anonymous)
    n_unread = 0

    if node.is_contributor(user):
        view_timestamp = datetime.strptime('01/01/70 17:00:00', '%m/%d/%y %H:%M:%S').isoformat()

        if user.comments_viewed_timestamp is None:
            user.comments_viewed_timestamp = {}
            user.save()

        if user.comments_viewed_timestamp.get(node._id, None):
            view_timestamp = user.comments_viewed_timestamp[node._id]

        n_unread = n_unread_comments(view_timestamp, comments, user)

    return {

        'comments': comments,
        'nUnread': n_unread
    }


def n_unread_comments(view_timestamp, comments, current_user):
    count = 0

    for comment in comments:
        if comment['author']['id'] != current_user._id:
            date_created = datetime.strptime(comment['dateCreated'], '%m/%d/%y %H:%M:%S').isoformat()
            date_modified = datetime.strptime(comment['dateModified'], '%m/%d/%y %H:%M:%S').isoformat()

            if date_created > view_timestamp or date_modified > view_timestamp:
                count += 1

    return count


@must_be_logged_in
@must_be_contributor_or_public
def edit_comment(**kwargs):

    auth = kwargs['auth']

    comment = kwargs_to_comment(kwargs, owner=True)

    content = request.json.get('content').strip()
    content = sanitize(content)
    if not content:
        raise HTTPError(http.BAD_REQUEST)
    if len(content) > settings.COMMENT_MAXLENGTH:
        raise HTTPError(http.BAD_REQUEST)

    comment.edit(
        content=content,
        auth=auth,
        save=True
    )

    return serialize_comment(comment, auth)


@must_be_logged_in
@must_be_contributor_or_public
def delete_comment(**kwargs):

    auth = kwargs['auth']
    comment = kwargs_to_comment(kwargs, owner=True)
    comment.delete(auth=auth, save=True)

    return {}


@must_be_logged_in
@must_be_contributor_or_public
def undelete_comment(**kwargs):

    auth = kwargs['auth']
    comment = kwargs_to_comment(kwargs, owner=True)
    comment.undelete(auth=auth, save=True)

    return {}


@must_be_logged_in
@must_be_contributor_or_public
def view_comments(**kwargs):
    node = kwargs['node'] or kwargs['project']
    user = get_current_user()

    if node.is_contributor(user):
        user.comments_viewed_timestamp[node._id] = datetime.utcnow().isoformat()
        user.save()
        list_comments(**kwargs)
    return {}


@must_be_logged_in
@must_be_contributor_or_public
def report_abuse(**kwargs):

    auth = kwargs['auth']
    user = auth.user

    comment = kwargs_to_comment(kwargs)

    category = request.json.get('category')
    text = request.json.get('text', '')
    if not category:
        raise HTTPError(http.BAD_REQUEST)

    try:
        comment.report_abuse(user, save=True, category=category, text=text)
    except ValueError:
        raise HTTPError(http.BAD_REQUEST)

    return {}


@must_be_logged_in
@must_be_contributor_or_public
def unreport_abuse(**kwargs):

    auth = kwargs['auth']
    user = auth.user

    comment = kwargs_to_comment(kwargs)

    try:
        comment.unreport_abuse(user, save=True)
    except ValueError:
        raise HTTPError(http.BAD_REQUEST)

    return {}
