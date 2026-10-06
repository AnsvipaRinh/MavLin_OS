/* mv-apple — MavLinOS Apple menu for xfce4-panel.
 *
 * Mavericks (10.9) Apple menu layout:
 *   About This Mac | System Preferences...
 *   ----
 *   Recent Items | Force Quit...
 *   ----
 *   Sleep | Restart... | Shut Down...
 *   ----
 *   Lock Screen | Log Out...
 *
 * Fidelity notes (see docs/DECISIONS.md):
 *  * Sleep / Restart / Shut Down / Log Out go through mv-power-ui, which
 *    shows the Mavericks alert with the 60 s countdown, battery footer and
 *    logind Can* gating.  Raw `systemctl` bypassed every one of those and
 *    also skipped the polkit path entirely.
 *  * If mv-power-ui is missing (partial install) we fall back to the plain
 *    systemctl call so the menu never becomes a dead item.
 *  * Menu titles carry mnemonics and items carry macOS-style accelerator
 *    glyphs, so the menu is reachable and readable without a mouse.
 *
 * License: GPL-2.0-or-later
 */
#include <gtk/gtk.h>
#include <libxfce4panel/libxfce4panel.h>

static void
launch (const gchar *command)
{
    GError *error = NULL;
    if (!g_spawn_command_line_async (command, &error) && error != NULL)
        g_error_free (error);
}

/* Sleep / Restart / Shut Down / Log Out via the Mavericks power dialog,
 * with a systemctl fallback when the helper is not installed. */
static void
launch_power (const gchar *action, const gchar *fallback)
{
    gchar *helper = g_find_program_in_path ("mv-power-ui");

    if (helper != NULL)
    {
        gchar *command = g_strdup_printf ("mv-power-ui %s", action);
        launch (command);
        g_free (command);
        g_free (helper);
        return;
    }

    launch (fallback);
}

static void
activate_command (GtkWidget *item, gpointer data)
{
    (void) data;
    launch ((const gchar *) g_object_get_data (G_OBJECT (item), "mv-command"));
}

static void
activate_power (GtkWidget *item, gpointer data)
{
    const gchar *action = g_object_get_data (G_OBJECT (item), "mv-power-action");
    const gchar *fallback = g_object_get_data (G_OBJECT (item), "mv-power-fallback");

    launch_power (action, fallback);
}

/* Mnemonic-aware label: macOS underlines the first letter of every menu
 * title and item.  GTK renders the underline for us when the label uses
 * the "use-underline" property and carries an "_" prefix. */
static GtkWidget *
menu_label (const gchar *text)
{
    GtkWidget *label = gtk_label_new_with_mnemonic (text);

    gtk_label_set_use_underline (GTK_LABEL (label), TRUE);
    gtk_label_set_xalign (GTK_LABEL (label), 0.0);
    gtk_widget_show (label);
    return label;
}

/* Right-aligned macOS accelerator column. */
static GtkWidget *
accel_label (const gchar *glyphs)
{
    GtkWidget *label = gtk_label_new (NULL);
    gchar *markup = g_markup_printf_escaped ("<span size=\"small\">%s</span>", glyphs);

    gtk_label_set_markup (GTK_LABEL (label), markup);
    gtk_label_set_xalign (GTK_LABEL (label), 1.0);
    gtk_widget_show (label);
    g_free (markup);
    return label;
}

static void
add_item (GtkWidget *menu, const gchar *label, const gchar *command,
          const gchar *accel)
{
    GtkWidget *item = gtk_menu_item_new ();
    GtkWidget *box = gtk_box_new (GTK_ORIENTATION_HORIZONTAL, 12);

    g_object_set_data_full (G_OBJECT (item), "mv-command", g_strdup (command), g_free);
    g_signal_connect (item, "activate", G_CALLBACK (activate_command), NULL);

    gtk_container_add (GTK_CONTAINER (box), menu_label (label));
    if (accel != NULL)
        gtk_container_add (GTK_CONTAINER (box), accel_label (accel));
    gtk_widget_show (box);
    gtk_container_add (GTK_CONTAINER (item), box);
    gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);
    gtk_widget_show (item);
}

static void
add_power_item (GtkWidget *menu, const gchar *label, const gchar *action,
                const gchar *fallback, const gchar *accel)
{
    GtkWidget *item = gtk_menu_item_new ();
    GtkWidget *box = gtk_box_new (GTK_ORIENTATION_HORIZONTAL, 12);

    g_object_set_data_full (G_OBJECT (item), "mv-power-action", g_strdup (action), g_free);
    g_object_set_data_full (G_OBJECT (item), "mv-power-fallback", g_strdup (fallback), g_free);
    g_signal_connect (item, "activate", G_CALLBACK (activate_power), NULL);

    gtk_container_add (GTK_CONTAINER (box), menu_label (label));
    if (accel != NULL)
        gtk_container_add (GTK_CONTAINER (box), accel_label (accel));
    gtk_widget_show (box);
    gtk_container_add (GTK_CONTAINER (item), box);
    gtk_menu_shell_append (GTK_MENU_SHELL (menu), item);
    gtk_widget_show (item);
}

static void
add_separator (GtkWidget *menu)
{
    GtkWidget *sep = gtk_separator_menu_item_new ();

    gtk_menu_shell_append (GTK_MENU_SHELL (menu), sep);
    gtk_widget_show (sep);
}

static void
popup_menu (GtkWidget *button, gpointer data)
{
    XfcePanelPlugin *plugin = XFCE_PANEL_PLUGIN (data);
    GtkWidget *menu = gtk_menu_new ();

    add_item (menu, "_About This Mac", "mv-about", NULL);
    add_item (menu, "System _Preferences...", "mv-settings", NULL);

    add_separator (menu);

    add_item (menu, "_Recent Items", "mv-recent-items", NULL);
    add_item (menu, "_Force Quit...", "mv-force-quit", "\u2325\u2318\u238b");

    add_separator (menu);

    add_power_item (menu, "S_leep", "sleep", "systemctl suspend", NULL);
    add_power_item (menu, "_Restart...", "restart", "systemctl reboot", NULL);
    add_power_item (menu, "_Shut Down...", "shutdown", "systemctl poweroff", NULL);

    add_separator (menu);

    add_item (menu, "_Lock Screen", "xfce4-screensaver-command --lock",
              "\u21e7\u2303\u2318Q");
    add_power_item (menu, "_Log Out...", "logout", "xfce4-session-logout", NULL);

    /* macOS has no tear-off arrow on the Apple menu.  The plain menu
     * constructor already defaults to tearoff=FALSE; the tear-off variant
     * is a different constructor, so nothing has to be undone here. */
    gtk_widget_show_all (menu);
    xfce_panel_plugin_popup_menu (plugin, GTK_MENU (menu), button, NULL);
}

static void
construct (XfcePanelPlugin *plugin)
{
    GtkWidget *button = gtk_button_new ();
    GtkWidget *label = gtk_image_new_from_icon_name ("mv-apple", GTK_ICON_SIZE_MENU);

    gtk_widget_set_name (label, "mavlinos-apple-menu");
    gtk_widget_set_tooltip_text (button, "MavLinOS Apple menu");
    gtk_container_add (GTK_CONTAINER (button), label);
    gtk_button_set_relief (GTK_BUTTON (button), GTK_RELIEF_NONE);
    gtk_container_add (GTK_CONTAINER (plugin), button);

    xfce_panel_plugin_add_action_widget (plugin, button);
    g_signal_connect (button, "clicked", G_CALLBACK (popup_menu), plugin);
    /* Small item: a menu-bar button must not claim the 48px action-button
     * slot.  XFCE_PANEL_PLUGIN_CONSTRUCTED() is already TRUE here — the flag
     * is set in xfce_panel_plugin_constructor(), before this function runs. */
    xfce_panel_plugin_set_small (plugin, TRUE);
    gtk_widget_show_all (GTK_WIDGET (plugin));
}

XFCE_PANEL_PLUGIN_REGISTER(construct);
