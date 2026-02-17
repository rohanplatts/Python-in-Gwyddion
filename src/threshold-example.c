#include "config.h"

#include <gtk/gtk.h>
#include <glib.h>
#include <glib/gstdio.h>

#include <errno.h>
#include <string.h>

#ifdef G_OS_WIN32
  #include <io.h>
  #define close _close
#else
  #include <unistd.h>
#endif

#include <libgwyddion/gwymacros.h>
#include <libgwymodule/gwymodule.h>
#include <libprocess/datafield.h>
#include <app/gwyapp.h>

#define RUN_MODES GWY_RUN_IMMEDIATE

static gboolean module_register(void);
static void     stm_python_bridge(GwyContainer *data, GwyRunType run, const gchar *name);

static void show_error(const gchar *msg)
{
    g_warning("%s", msg);
    GtkWidget *d = gtk_message_dialog_new(NULL, GTK_DIALOG_MODAL,
                                          GTK_MESSAGE_ERROR, GTK_BUTTONS_OK,
                                          "%s", msg);
    gtk_dialog_run(GTK_DIALOG(d));
    gtk_widget_destroy(d);
}


static gboolean
write_npy_f64_2d(const char *path, const gdouble *a, gint ny, gint nx, GError **err)
{
    FILE *f = g_fopen(path, "wb");
    if (!f) {
        g_set_error(err, G_FILE_ERROR, g_file_error_from_errno(errno),
                    "Cannot open for write: %s", path);
        return FALSE;
    }

    const unsigned char magic[] = {0x93,'N','U','M','P','Y'};
    const unsigned char ver[]   = {1,0};

    gchar *hdr = g_strdup_printf("{'descr': '<f8', 'fortran_order': False, 'shape': (%d, %d), }",
                                 ny, nx);
    gsize hdr_len = strlen(hdr);

    
    gsize pre = 6 + 2 + 2; 
    gsize pad = (16 - ((pre + hdr_len + 1) % 16)) % 16;

    gchar *hdr_padded = g_malloc(hdr_len + pad + 1);
    memcpy(hdr_padded, hdr, hdr_len);
    memset(hdr_padded + hdr_len, ' ', pad);
    hdr_padded[hdr_len + pad] = '\n';

    guint16 hlen = (guint16)(hdr_len + pad + 1);
    unsigned char hlen_le[2] = {(unsigned char)(hlen & 0xFF),
                                (unsigned char)((hlen >> 8) & 0xFF)};

    if (fwrite(magic, 1, 6, f) != 6 ||
        fwrite(ver,   1, 2, f) != 2 ||
        fwrite(hlen_le, 1, 2, f) != 2 ||
        fwrite(hdr_padded, 1, hlen, f) != hlen) {
        g_set_error(err, G_FILE_ERROR, g_file_error_from_errno(errno),
                    "Write failed: %s", path);
        fclose(f);
        g_free(hdr);
        g_free(hdr_padded);
        return FALSE;
    }

    gsize n = (gsize)ny * (gsize)nx;
    if (fwrite(a, sizeof(gdouble), n, f) != n) {
        g_set_error(err, G_FILE_ERROR, g_file_error_from_errno(errno),
                    "Write failed: %s", path);
        fclose(f);
        g_free(hdr);
        g_free(hdr_padded);
        return FALSE;
    }

    fclose(f);
    g_free(hdr);
    g_free(hdr_padded);
    return TRUE;
}

static gboolean
read_npy_f64_2d(const char *path, gdouble **out, gint *ny, gint *nx, GError **err)
{
    *out = NULL; *ny = 0; *nx = 0;

    FILE *f = g_fopen(path, "rb");
    if (!f) {
        g_set_error(err, G_FILE_ERROR, g_file_error_from_errno(errno),
                    "Cannot open for read: %s", path);
        return FALSE;
    }

    unsigned char magic[6], ver[2], hlen_le[2];
    if (fread(magic, 1, 6, f) != 6 || memcmp(magic, "\x93NUMPY", 6) != 0 ||
        fread(ver,   1, 2, f) != 2 || ver[0] != 1 || ver[1] != 0 ||
        fread(hlen_le, 1, 2, f) != 2) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Not a supported .npy (need v1.0): %s", path);
        fclose(f);
        return FALSE;
    }

    guint16 hlen = (guint16)(hlen_le[0] | (hlen_le[1] << 8));
    gchar *hdr = g_malloc(hlen + 1);
    if (fread(hdr, 1, hlen, f) != hlen) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Header read failed: %s", path);
        fclose(f);
        g_free(hdr);
        return FALSE;
    }
    hdr[hlen] = 0;

    if (!strstr(hdr, "'descr': '<f8'") && !strstr(hdr, "\"descr\": \"<f8\"")) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Output .npy must be float64 '<f8': %s", path);
        fclose(f);
        g_free(hdr);
        return FALSE;
    }
    if (strstr(hdr, "fortran_order': True") || strstr(hdr, "fortran_order\": true")) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Output .npy must be C-order (fortran_order False): %s", path);
        fclose(f);
        g_free(hdr);
        return FALSE;
    }

    char *p = strchr(hdr, '(');
    int a=0,b=0;
    if (!p || sscanf(p, "(%d, %d", &a, &b) != 2 || a <= 0 || b <= 0) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Cannot parse shape (ny,nx) in .npy header: %s", path);
        fclose(f);
        g_free(hdr);
        return FALSE;
    }
    *ny = a; *nx = b;

    gsize n = (gsize)(*ny) * (gsize)(*nx);
    gdouble *buf = g_malloc(n * sizeof(gdouble));
    if (fread(buf, sizeof(gdouble), n, f) != n) {
        g_set_error(err, G_FILE_ERROR, 0,
                    "Data read failed: %s", path);
        fclose(f);
        g_free(hdr);
        g_free(buf);
        return FALSE;
    }

    fclose(f);
    g_free(hdr);
    *out = buf;
    return TRUE;
}


static GwyModuleInfo module_info = {
    GWY_MODULE_ABI_VERSION,
    &module_register,
    N_("Runs an external Python script on the current channel via .npy I/O."),
    "Rohan Platts (local module)",
    "1.0",
    "Local",
    "2026",
};

GWY_MODULE_QUERY(module_info)

static gboolean
module_register(void)
{
    gwy_process_func_register("stm_python_bridge",
                              (GwyProcessFunc)&stm_python_bridge,
                              N_("/STM/_Run Python Script"),
                              NULL,
                              RUN_MODES,
                              GWY_MENU_FLAG_DATA,
                              N_("Export channel to .npy, run Python, import result."));
    return TRUE;
}

static void
stm_python_bridge(GwyContainer *data, GwyRunType run, const gchar *name)
{
    (void)name;
    g_return_if_fail(run & RUN_MODES);

    GwyDataField *dfield = NULL;
    GQuark quark = 0;
    gint id = -1;

    gwy_app_data_browser_get_current(GWY_APP_DATA_FIELD, &dfield,
                                     GWY_APP_DATA_FIELD_KEY, &quark,
                                     GWY_APP_DATA_FIELD_ID, &id,
                                     0);
    if (!dfield) {
        show_error("No current data field.");
        return;
    }

    const gchar *pyexe = g_getenv("GWY_PYTHON_EXE");
    const gchar *pyscript = g_getenv("GWY_PYTHON_SCRIPT");
    if (!pyexe || !*pyexe || !pyscript || !*pyscript) {
        show_error("Set GWY_PYTHON_EXE and GWY_PYTHON_SCRIPT before launching Gwyddion.");
        return;
    }

    gint nx = gwy_data_field_get_xres(dfield);
    gint ny = gwy_data_field_get_yres(dfield);
    const gdouble *src = gwy_data_field_get_data_const(dfield);

    GError *err = NULL;
    gchar *inpath = NULL;
    gchar *outpath = NULL;

    gint fd_in = g_file_open_tmp("gwy_py_in_XXXXXX.npy", &inpath, &err);
    if (fd_in < 0) {
        show_error(err ? err->message : "Failed to create temp input file.");
        g_clear_error(&err);
        return;
    }
    close(fd_in);

    gint fd_out = g_file_open_tmp("gwy_py_out_XXXXXX.npy", &outpath, &err);
    if (fd_out < 0) {
        show_error(err ? err->message : "Failed to create temp output file.");
        g_clear_error(&err);
        g_unlink(inpath);
        g_free(inpath);
        return;
    }
    close(fd_out);

    if (!write_npy_f64_2d(inpath, src, ny, nx, &err)) {
        show_error(err ? err->message : "Failed to write input .npy.");
        g_clear_error(&err);
        g_unlink(inpath); g_unlink(outpath);
        g_free(inpath); g_free(outpath);
        return;
    }

    gchar *argv[] = {(gchar*)pyexe, (gchar*)pyscript, inpath, outpath, NULL};
    gchar *std_out = NULL;
    gchar *std_err = NULL;
    gint status = 0;

    if (!g_spawn_sync(NULL, argv, NULL, 0, NULL, NULL, &std_out, &std_err, &status, &err)) {
        show_error(err ? err->message : "Failed to run Python.");
        g_clear_error(&err);
        g_free(std_out); g_free(std_err);
        g_unlink(inpath); g_unlink(outpath);
        g_free(inpath); g_free(outpath);
        return;
    }

    if (status != 0) {
        show_error((std_err && *std_err) ? std_err : "Python exited non-zero.");
        g_free(std_out); g_free(std_err);
        g_unlink(inpath); g_unlink(outpath);
        g_free(inpath); g_free(outpath);
        return;
    }

    g_free(std_out);
    g_free(std_err);

    gdouble *dst = NULL;
    gint ony=0, onx=0;
    if (!read_npy_f64_2d(outpath, &dst, &ony, &onx, &err)) {
        show_error(err ? err->message : "Failed to read output .npy.");
        g_clear_error(&err);
        g_unlink(inpath); g_unlink(outpath);
        g_free(inpath); g_free(outpath);
        return;
    }

    if (ony != ny || onx != nx) {
        show_error("Output .npy shape mismatch (must match input).");
        g_free(dst);
        g_unlink(inpath); g_unlink(outpath);
        g_free(inpath); g_free(outpath);
        return;
    }

    gwy_app_undo_qcheckpointv(data, 1, &quark);
    memcpy(gwy_data_field_get_data(dfield), dst, (gsize)nx*(gsize)ny*sizeof(gdouble));
    g_free(dst);

    gwy_data_field_data_changed(dfield);
    gwy_app_channel_log_add_proc(data, id, id);

    g_unlink(inpath);
    g_unlink(outpath);
    g_free(inpath);
    g_free(outpath);
}
