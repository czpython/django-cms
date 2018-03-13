from __future__ import unicode_literals
from collections import defaultdict, deque
import json

from django.utils.encoding import force_text
from django.utils.six import text_type
from django.utils.translation import override as force_language, ugettext

from cms.constants import PLACEHOLDER_TOOLBAR_JS, PLUGIN_TOOLBAR_JS


def get_placeholder_toolbar_js(placeholder, allowed_plugins=None):
    label = placeholder.get_label() or ''
    help_text = ugettext(
        'Add plugin to placeholder "%(placeholder_label)s"'
    ) % {'placeholder_label': label}

    data = {
        'type': 'placeholder',
        'name': force_text(label),
        'placeholder_id': text_type(placeholder.pk),
        'plugin_restriction': allowed_plugins or [],
        'addPluginHelpTitle': force_text(help_text),
        'urls': {
            'add_plugin': placeholder.get_add_url(),
            'copy_plugin': placeholder.get_copy_url(),
        }
    }
    return PLACEHOLDER_TOOLBAR_JS % {'pk': placeholder.pk, 'config': json.dumps(data)}


def get_plugin_toolbar_info(plugin, children=None, parents=None):
    data = plugin.get_plugin_info(children=children, parents=parents)
    help_text = ugettext(
        'Add plugin to %(plugin_name)s'
    ) % {'plugin_name': data['plugin_name']}

    data['onClose'] = False
    data['addPluginHelpTitle'] = force_text(help_text)
    data['plugin_order'] = ''
    data['plugin_restriction'] = children or []
    data['plugin_parent_restriction'] = parents or []
    return data


def get_plugin_toolbar_js(plugin, children=None, parents=None):
    data = get_plugin_toolbar_info(
        plugin,
        children=children,
        parents=parents,
    )
    return PLUGIN_TOOLBAR_JS % {'pk': plugin.pk, 'config': json.dumps(data)}


def get_plugin_tree_as_json(request, plugins):
    from cms.utils.plugins import (
        downcast_plugins,
        get_plugin_class,
        get_plugin_restrictions,
    )

    tree_data = []
    tree_structure = []
    restrictions = {}
    toolbar = get_toolbar_from_request(request)
    template = toolbar.templates.drag_item_template
    placeholder = plugins[0].placeholder
    host_page = placeholder.page
    copy_to_clipboard = placeholder.pk == toolbar.clipboard.pk
    plugins = downcast_plugins(plugins, select_placeholder=True)
    get_plugin_info = get_plugin_toolbar_info

    delayed = defaultdict(deque)

    with force_language(toolbar.toolbar_language):
        plugins = list(plugins)
        plugin_ids = frozenset(plugin.pk for plugin in plugins)

        for plugin in reversed(plugins):
            plugin_class = get_plugin_class(plugin.plugin_type)
            child_classes, parent_classes = get_plugin_restrictions(
                plugin=plugin,
                page=host_page,
                restrictions_cache=restrictions,
            )
            plugin_info = get_plugin_info(
                plugin,
                children=child_classes,
                parents=parent_classes,
            )
            context = {
                'plugin': plugin,
                'request': request,
                'clipboard': copy_to_clipboard,
                'cms_toolbar': toolbar,
                'allow_children': plugin_class.allow_children,
                'disable_child_plugins': plugin_class.disable_child_plugins,
            }

            if plugin.pk in delayed:
                context['children'] = '\n'.join(delayed.pop(plugin.pk))

            content = template.render(context)

            if plugin.parent_id and plugin.parent_id in plugin_ids:
                # Continue aggregating the content
                delayed[plugin.parent_id].appendleft(content)
            else:
                # The plugin has no parent or we're rendering a sub-tree
                tree_structure.append(content)
            tree_data.append(plugin_info)
    return json.dumps({'html': '\n'.join(tree_structure), 'plugins': tree_data})


def get_toolbar_from_request(request):
    from .toolbar import EmptyToolbar

    return getattr(request, 'toolbar', EmptyToolbar(request))
