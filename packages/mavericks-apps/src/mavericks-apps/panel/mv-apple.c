#include <gtk/gtk.h>
#include <libxfce4panel/libxfce4panel.h>

static void launch(const gchar *command)
{
    GError *error = NULL;
    if (!g_spawn_command_line_async(command, &error) && error != NULL)
        g_error_free(error);
}

static void activate_command(GtkWidget *item, gpointer data)
{
    (void)data;
    launch((const gchar *)g_object_get_data(G_OBJECT(item), "mv-command"));
}

static void add_item(GtkWidget *menu, const gchar *label, const gchar *command)
{
    GtkWidget *item = gtk_menu_item_new_with_label(label);
    g_object_set_data_full(G_OBJECT(item), "mv-command", g_strdup(command), g_free);
    g_signal_connect(item, "activate", G_CALLBACK(activate_command), NULL);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
    gtk_widget_show(item);
}

static void popup_menu(GtkWidget *button, gpointer data)
{
    XfcePanelPlugin *plugin = XFCE_PANEL_PLUGIN(data);
    GtkWidget *menu = gtk_menu_new();

    add_item(menu, "About This Mac", "mv-about");
    add_item(menu, "System Preferences…", "mv-settings");

    GtkWidget *sep = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), sep);
    gtk_widget_show(sep);

    add_item(menu, "Recent Items", "mv-recent-items");
    add_item(menu, "Force Quit…", "mv-force-quit");

    sep = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), sep);
    gtk_widget_show(sep);

    add_item(menu, "Sleep", "systemctl suspend");
    add_item(menu, "Restart…", "systemctl reboot");
    add_item(menu, "Shut Down…", "systemctl poweroff");

    sep = gtk_separator_menu_item_new();
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), sep);
    gtk_widget_show(sep);

    add_item(menu, "Lock Screen", "xfce4-screensaver-command --lock");
    add_item(menu, "Log Out…", "xfce4-session-logout");

    gtk_widget_show_all(menu);
    xfce_panel_plugin_popup_menu(plugin, GTK_MENU(menu), button, NULL);
}

static void construct(XfcePanelPlugin *plugin)
{
    GtkWidget *button = gtk_button_new();
    GtkWidget *label = gtk_image_new_from_icon_name("mv-apple", GTK_ICON_SIZE_MENU);
    gtk_widget_set_name(label, "mavlinos-apple-menu");
    gtk_widget_set_tooltip_text(button, "Apple menu");
    gtk_container_add(GTK_CONTAINER(button), label);
    gtk_button_set_relief(GTK_BUTTON(button), GTK_RELIEF_NONE);
    gtk_container_add(GTK_CONTAINER(plugin), button);
    xfce_panel_plugin_add_action_widget(plugin, button);
    g_signal_connect(button, "clicked", G_CALLBACK(popup_menu), plugin);
    xfce_panel_plugin_set_small(plugin, TRUE);
    gtk_widget_show_all(GTK_WIDGET(plugin));
}

XFCE_PANEL_PLUGIN_REGISTER(construct);
