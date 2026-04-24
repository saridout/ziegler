import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.axes import Axes as mAxes
from matplotlib.artist import Artist
import numpy as np

import inspect
import copy

widths = {"PR": 3+3/8,
          "eLife": 5.6,
          "PR_full": 7.08,
          "AnnRev": 5.06,
          "PNAS": 3.42,
          "PNAS_mid": 4.5,
          "PNAS_full": 7.0,
          "poster": 10,
          "powerpoint": 11.5
          }

colors = {"cadmium_red": "#D22B2B",
          "cobalt_blue": "#0047AB",
          "sean_green": "#1E8449"
          }

class Axes:
    """
    Presents an API that resembles the matplotlib "axis" API.
    However, nothing is actually drawn until "render" is called.
    Internally, we just a queue of commands for a real axis object
    """

    def __init__(self, axis_label_fontsize=12, panel_label_fontsize=12, tick_label_fontsize=None):
        self.f_queue = []
        self.args_queue = []
        self.kwargs_queue = []
        self.callable_args_queue = []
        self.axis_label_fontsize=axis_label_fontsize
        self.panel_label_fontsize=panel_label_fontsize
        self.tick_label_fontsize=tick_label_fontsize

        self.plt_f_queue = []
        self.plt_args_queue = []
        self.plt_kwargs_queue = []



    #import all matplotlib Axes member functions
    all_f = inspect.getmembers(mAxes, predicate=inspect.isfunction)

    def mapped_function(g, **default_kwargs):
        def f(self, *args, **kwargs):
            self.f_queue.append(g)
            self.args_queue.append(args)
            self.kwargs_queue.append(dict({kw: self.__dict__[default_kwargs[kw]] for kw in default_kwargs}, **kwargs))
        return f

    for name, g in all_f:
        if name == "set_xlabel" or name == "set_ylabel":
            f = mapped_function(g, fontsize="axis_label_fontsize")
        else:
            f = mapped_function(g)

        if not name[0] == "_":
            locals()[name] = f

    def colorbar(self, **kwargs):
        self.plt_f_queue.append(plt.colorbar)
        self.plt_args_queue.append([])
        self.plt_kwargs_queue.append(dict(**kwargs, cax=self)) #this requires special handling in render

    def label_panel(self, **kwargs):
        def _label_panel(ax, text=None, hpos=None, vpos=None, gap_pt=None):
            bbox = ax.get_window_extent().transformed(ax.figure.dpi_scale_trans.inverted())
            w, h = bbox.width, bbox.height
            rel_dx =  (gap_pt/72)/w
            rel_dy =  (gap_pt/72)/h

            assert ax.get_xscale() == 'log' or ax.get_xscale() == 'linear'
            assert ax.get_yscale() == 'log' or ax.get_yscale() == 'linear'

            y_tf = np.log if ax.get_yscale() == 'log' else lambda x:x
            x_tf = np.log if ax.get_xscale() == 'log' else lambda x:x
            y_inv = np.exp if ax.get_yscale() == 'log' else lambda x:x
            x_inv = np.exp if ax.get_xscale() == 'log' else lambda x:x

            if hpos == "left":
                x = x_inv(rel_dx*(x_tf(ax.get_xlim()[1]) - x_tf(ax.get_xlim()[0])) + x_tf(ax.get_xlim()[0]))
            if hpos == "right":
                x = x_inv(rel_dx*(x_tf(ax.get_xlim()[0]) - x_tf(ax.get_xlim()[1])) + x_tf(ax.get_xlim()[1]))
            if vpos == "bottom":
                y = y_inv(rel_dy*(y_tf(ax.get_ylim()[1]) - y_tf(ax.get_ylim()[0])) + y_tf(ax.get_ylim()[0]))
            if vpos == "top":
                y = y_inv(rel_dy*(y_tf(ax.get_ylim()[0]) - y_tf(ax.get_ylim()[1])) + y_tf(ax.get_ylim()[1]))
            if hpos == "out":
                rel_dx = -rel_dx
                x = x_inv(rel_dx*(x_tf(ax.get_xlim()[1]) - x_tf(ax.get_xlim()[0])) + x_tf(ax.get_xlim()[0]))
                rel_dy = 0
                y = y_inv(rel_dy*(y_tf(ax.get_ylim()[0]) - y_tf(ax.get_ylim()[1])) + y_tf(ax.get_ylim()[1]))
                hpos="right"
                vpos="center"

            ax.text(x, y, text, verticalalignment=vpos, horizontalalignment=hpos, fontsize=self.panel_label_fontsize)
        self.f_queue.append(_label_panel)
        self.args_queue.append([])
        self.kwargs_queue.append(kwargs)

    def render(self, ax):
        for f, args, kwargs in zip(self.f_queue, self.args_queue, self.kwargs_queue):
            # Figure.render() draws multiple temporary figures; artists must be fresh each pass.
            has_artist = (any(isinstance(arg, Artist) for arg in args)
                          or any(isinstance(v, Artist) for v in kwargs.values()))
            if has_artist:
                _ = f(ax, *copy.deepcopy(args), **copy.deepcopy(kwargs))
            else:
                _ = f(ax, *args, **kwargs)
        for g, args, _kwargs in zip(self.plt_f_queue, self.plt_args_queue, self.plt_kwargs_queue):
            kwargs = {}
            for key in _kwargs:
                if _kwargs[key] == self:
                    kwargs[key] = ax
                else:
                    kwargs[key] = _kwargs[key]

            _ = g(*args, **kwargs)

            if self.tick_label_fontsize is not None:
                ax.tick_params(axis='both', which='major', labelsize=self.tick_label_fontsize)

class Figure:

    def __init__(self, width=4, aspect_ratio=1,
                 axis_label_fontsize=12, panel_label_fontsize=12,
                 column_widths=[1.0,], row_heights=[1.0,],
                 inner_margin_pt=6, top_margin_pt=0, left_margin_pt=0, right_margin_pt=0,
                 ax_line_scale=1, line_scale=1, bare_top=True, bare_right=True,
                 tick_label_fontsize=None,
                 rc_params=None):
        try:
            self.figure_width = float(width) #inches
        except (ValueError, TypeError):
            self.set_figure_width(journal=width)
        self.panel_label_fontsize = panel_label_fontsize #pt
        self.aspect_ratio = aspect_ratio #h/w

        # Detect whether row_heights or column_widths is a list-of-lists, indicating
        # an irregular grid.
        #
        # col_major: row_heights is a list-of-lists (one array per column).
        #   axes[col][row]; each column has its own independent set of rows.
        #
        # row_major: column_widths is a list-of-lists (one array per row).
        #   axes[row][col]; each row has its own independent set of columns.
        #
        # regular: both are flat arrays. axes[row][col] as before.
        rows_irregular = np.ndim(row_heights[0]) > 0
        cols_irregular = np.ndim(column_widths[0]) > 0
        if rows_irregular and cols_irregular:
            raise ValueError(
                "row_heights and column_widths cannot both be irregular (list-of-lists)"
            )

        def _make_ax():
            return Axes(axis_label_fontsize=axis_label_fontsize,
                        panel_label_fontsize=panel_label_fontsize,
                        tick_label_fontsize=tick_label_fontsize)

        if rows_irregular:
            self._layout = 'col_major'
            self.column_widths = np.array(column_widths, dtype=float) / np.sum(column_widths)
            if len(row_heights) != len(column_widths):
                raise ValueError(
                    "When row_heights is a list-of-lists, it must have one entry per column"
                )
            self.row_heights = [np.array(rh, dtype=float) / np.sum(rh) for rh in row_heights]
            self.axes = [[_make_ax() for _ in rh] for rh in row_heights]
        elif cols_irregular:
            self._layout = 'row_major'
            self.row_heights = np.array(row_heights, dtype=float) / np.sum(row_heights)
            if len(column_widths) != len(row_heights):
                raise ValueError(
                    "When column_widths is a list-of-lists, it must have one entry per row"
                )
            self.column_widths = [np.array(cw, dtype=float) / np.sum(cw) for cw in column_widths]
            self.axes = [[_make_ax() for _ in cw] for cw in column_widths]
        else:
            self._layout = 'regular'
            self.column_widths = np.array(column_widths, dtype=float) / np.sum(column_widths)
            self.row_heights = np.array(row_heights, dtype=float) / np.sum(row_heights)
            self.axes = np.array([
                [_make_ax() for _ in column_widths]
                for _ in row_heights
            ])

        self.inner_margin_pt = inner_margin_pt
        self.top_margin_pt = top_margin_pt
        self.left_margin_pt = left_margin_pt
        self.right_margin_pt = right_margin_pt
        self.axis_label_fontsize = axis_label_fontsize
        self.tick_label_fontsize = tick_label_fontsize

        self.bare_top = bare_top
        self.bare_right = bare_right

        if rc_params is None:
            self.rc_params = {"xtick.direction": 'in', "ytick.direction": 'in'}
        else:
            self.rc_params = rc_params

        self.rc_params['axes.linewidth'] =  0.8*ax_line_scale
        self.rc_params['xtick.major.width'] =  0.8*ax_line_scale
        self.rc_params['ytick.major.width'] =  0.8*ax_line_scale
        self.rc_params['xtick.minor.width'] =  0.6*ax_line_scale
        self.rc_params['ytick.minor.width'] =  0.6*ax_line_scale

        self.rc_params['lines.linewidth'] =  1.5*line_scale

        #in general, you want to avoid calling functions of the matplotlib figure class
        #however, we do implement a couple
        self.f_queue = []
        self.args_queue = []
        self.kwargs_queue = []
        self.artist_queue = []
        self.artists = {}

    def _init_margins(self):
        """Return zero-initialized (h_margins, v_margins) appropriate for the current layout."""
        if self._layout == 'col_major':
            n_cols = len(self.column_widths)
            h_margins = [0.0] * (n_cols + 1)
            v_margins = [[0.0] * (len(rh) + 1) for rh in self.row_heights]
        elif self._layout == 'row_major':
            n_rows = len(self.row_heights)
            h_margins = [[0.0] * (len(cw) + 1) for cw in self.column_widths]
            v_margins = [0.0] * (n_rows + 1)
        else:
            h_margins = [0.0] * (len(self.column_widths) + 1)
            v_margins = [0.0] * (len(self.row_heights) + 1)
        return h_margins, v_margins

    def set_figure_width(self, width_inches=None, journal=None):
        if width_inches is not None:
            self.figure_width = width_inches
        else:
            self.figure_width = widths[journal]

    def hide_internal_labels(self, x=True, y=True):
        if self._layout == 'col_major':
            # axes[col][row]
            if x:
                for col in self.axes:
                    for ax in col[:-1]:  # all but last row in each column
                        ax.set_xticklabels([])
            if y:
                for col in self.axes[1:]:  # all but first column
                    for ax in col:
                        ax.set_yticklabels([])
        elif self._layout == 'row_major':
            # axes[row][col]
            if x:
                for row in self.axes[:-1]:  # all but last row
                    for ax in row:
                        ax.set_xticklabels([])
            if y:
                for row in self.axes:
                    for ax in row[1:]:  # all but first column in each row
                        ax.set_yticklabels([])
        else:
            # regular: axes[row][col]
            if x:
                for row in self.axes[:-1]:
                    for ax in row:
                        ax.set_xticklabels([])
            if y:
                for row in self.axes:
                    for ax in row[1:]:
                        ax.set_yticklabels([])

    def mapped_function(g, artist_key, **default_kwargs):
        def f(self, *args, **kwargs):
            self.f_queue.append(g)
            self.args_queue.append(args)
            self.kwargs_queue.append(dict({kw: self.__dict__[default_kwargs[kw]] for kw in default_kwargs}, **kwargs))
            self.artist_queue.append(artist_key)

        return f

    supxlabel = mapped_function(mpl.figure.Figure.supxlabel, "supxlabel", fontsize="axis_label_fontsize")
    supylabel = mapped_function(mpl.figure.Figure.supylabel, "supylabel", fontsize="axis_label_fontsize")

    def render(self):
        """
        The workhorse.
        """
        #first render with no margins and figure out how much space we need to make
        h_margins, v_margins = self._init_margins()
        with mpl.rc_context(self.rc_params):
            fig, axes = self.render_fixed_margins(h_margins, v_margins)
            fig.canvas.draw() #force draw so bboxes are valid outside Jupyter
            h_margins, v_margins = self.correct_margins(fig, axes, h_margins, v_margins)
            _ = plt.clf() #if working interactively, hide the "test" plot
            fig, axes = self.render_fixed_margins(h_margins, v_margins)
            #need a second correction pass for a higher-order error my formula doesn't account for;
            #this arises if tick labels (rather than axis labels) are the things sticking into the margins
            #One day, I will try to figure out how to apply the exact correction instead
            fig.canvas.draw() #force draw so bboxes are valid outside Jupyter
            h_margins, v_margins = self.correct_margins(fig, axes, h_margins, v_margins)
            _ = plt.clf()
            fig, axes = self.render_fixed_margins(h_margins, v_margins)

        return fig, axes

    def _render_artists(self, fig):
        """Draw queued figure-level artists (supxlabel, supylabel, etc.)."""
        self.artists = {}
        for f, artist_key, args, kwargs in zip(
            self.f_queue, self.artist_queue, self.args_queue, self.kwargs_queue
        ):
            if artist_key is None:
                f(fig, *args, **kwargs)
            else:
                self.artists[artist_key] = f(fig, *args, **kwargs)

    def render_fixed_margins(self, h_margins, v_margins):

        w = self.figure_width
        h = self.aspect_ratio * self.figure_width
        fig = plt.figure(figsize=(w, h))

        if self._layout == 'col_major':
            # axes[col][row]; each column has its own v_margins and row_heights
            real_column_widths = self.column_widths * (1 - sum(h_margins))
            axes = []
            X = 0.0
            for n, (col, col_row_heights) in enumerate(zip(self.axes, self.row_heights)):
                col_v_margins = v_margins[n]
                real_row_heights = col_row_heights * (1 - sum(col_v_margins))
                axes.append([])
                X += h_margins[n]
                Y = 1.0
                for m, srax in enumerate(col):
                    Y -= col_v_margins[m]
                    Y -= real_row_heights[m]
                    ax = fig.add_axes([X, Y, real_column_widths[n], real_row_heights[m]])
                    srax.render(ax)
                    axes[-1].append(ax)
                X += real_column_widths[n]

        elif self._layout == 'row_major':
            # axes[row][col]; each row has its own h_margins and column_widths
            real_row_heights = self.row_heights * (1 - sum(v_margins))
            axes = []
            Y = 1.0
            for m, (row, row_col_widths) in enumerate(zip(self.axes, self.column_widths)):
                row_h_margins = h_margins[m]
                real_col_widths = row_col_widths * (1 - sum(row_h_margins))
                axes.append([])
                Y -= v_margins[m]
                Y -= real_row_heights[m]
                X = 0.0
                for n, srax in enumerate(row):
                    X += row_h_margins[n]
                    ax = fig.add_axes([X, Y, real_col_widths[n], real_row_heights[m]])
                    srax.render(ax)
                    axes[-1].append(ax)
                    X += real_col_widths[n]

        else:
            # regular: axes[row][col]
            real_column_widths = self.column_widths * (1 - sum(h_margins))
            real_row_heights = self.row_heights * (1 - sum(v_margins))
            axes = []
            Y = 1.0
            for m, row in enumerate(self.axes):
                axes.append([])
                Y -= v_margins[m]
                Y -= real_row_heights[m]
                X = 0.0
                for n, srax in enumerate(row):
                    X += h_margins[n]
                    ax = fig.add_axes([X, Y, real_column_widths[n], real_row_heights[m]])
                    X += real_column_widths[n]
                    srax.render(ax)
                    axes[-1].append(ax)

        self._render_artists(fig)
        return fig, axes

    def bbox_pix(self, ax, is_bottom_row, is_left_col):
        """
        Return the tight bounding box of ax in pixel coordinates, extended to
        include supxlabel / supylabel if present and this panel is on the
        relevant edge.
        """
        bounds = np.array(ax.get_tightbbox().bounds) #x0, y0, width, height

        if "supxlabel" in self.artists and is_bottom_row:
            #want to extend bbox downward
            xlabel_bounds = self.artists["supxlabel"].get_window_extent().bounds
            new_height = xlabel_bounds[1] + xlabel_bounds[3] + bounds[3]
            bounds[1] = bounds[1] - (xlabel_bounds[1] + xlabel_bounds[3])
            bounds[3] = new_height

        if "supylabel" in self.artists and is_left_col:
            #want to extend bbox leftward
            ylabel_bounds = self.artists["supylabel"].get_window_extent().bounds
            new_width = ylabel_bounds[0] + ylabel_bounds[2] + bounds[2]
            bounds[0] = bounds[0] - (ylabel_bounds[0] + ylabel_bounds[2])
            bounds[2] = new_width

        return bounds

    def _bbox_rel(self, ax, is_bottom_row, is_left_col, w, h, dpi):
        """Return bbox_pix normalized to figure dimensions."""
        bp = self.bbox_pix(ax, is_bottom_row, is_left_col)
        bi = bp / dpi
        return [bi[0] / w, bi[1] / h, bi[2] / w, bi[3] / h]

    def correct_margins(self, fig, axes, h_margins, v_margins):

        w = self.figure_width
        h = self.aspect_ratio * self.figure_width
        dpi = fig.dpi
        inner_x_margin = (self.inner_margin_pt/72) / w
        inner_y_margin = (self.inner_margin_pt/72) / h
        left_margin = (self.left_margin_pt/72) / w
        top_margin = (self.top_margin_pt/72) / h
        right_margin = (self.right_margin_pt/72) / w

        if self.bare_right:
            right_margin += self.rc_params['axes.linewidth'] / (2*72*w)
        if self.bare_top:
            top_margin += self.rc_params['axes.linewidth'] / (2*72*w)

        if self._layout == 'col_major':
            # ---- Vertical margins: independent per column ----
            for n, col_axes in enumerate(axes):
                col_v_margins = v_margins[n]
                n_rows = len(col_axes)
                bottom_edge = 1.0
                min_bottom = 1.0
                for m, ax in enumerate(col_axes):
                    br = self._bbox_rel(ax, m == n_rows - 1, n == 0, w, h, dpi)
                    top_edge = br[1] + br[3] - sum(col_v_margins[:m+1])
                    y_delta = top_edge - bottom_edge + (inner_y_margin if m > 0 else top_margin)
                    if y_delta > 0:
                        col_v_margins[m] += y_delta
                    if br[1] + col_v_margins[-1] < 0:
                        col_v_margins[-1] = -br[1]
                    min_bottom = min(min_bottom, br[1] - sum(col_v_margins[:m+1]))
                    bottom_edge = min_bottom

            # ---- Equalize top/bottom margins so all columns share the same outer edges ----
            shared_top = max(vm[0] for vm in v_margins)
            shared_bot = max(vm[-1] for vm in v_margins)
            for vm in v_margins:
                vm[0] = shared_top
                vm[-1] = shared_bot

            # ---- For columns with the same row count, equalize internal margins so
            #      row boundaries land at the same Y positions across those columns ----
            from collections import defaultdict
            col_groups = defaultdict(list)
            for n, vm in enumerate(v_margins):
                col_groups[len(vm) - 1].append(n)  # key = number of rows
            for col_indices in col_groups.values():
                if len(col_indices) > 1:
                    n_internal = len(v_margins[col_indices[0]]) - 2  # internal boundaries
                    for k in range(1, n_internal + 1):
                        shared = max(v_margins[n][k] for n in col_indices)
                        for n in col_indices:
                            v_margins[n][k] = shared

            # ---- Horizontal margins: shared across all columns ----
            max_right_edge = 0.0
            for n, col_axes in enumerate(axes):
                n_rows = len(col_axes)
                # tight bbox extent across all rows of this column
                min_left = min(
                    self._bbox_rel(ax, m == n_rows - 1, n == 0, w, h, dpi)[0]
                    for m, ax in enumerate(col_axes)
                )
                max_right = max(
                    sum(self._bbox_rel(ax, m == n_rows - 1, n == 0, w, h, dpi)[0:3:2])
                    for m, ax in enumerate(col_axes)
                )
                left_edge = min_left + sum(h_margins[:n+1])
                x_delta = max_right_edge - left_edge + (inner_x_margin if n > 0 else left_margin)
                if x_delta > 0:
                    h_margins[n] += x_delta
                max_right_edge = max(max_right + sum(h_margins[:n+1]), max_right_edge)
                if max_right > 1 - right_margin + h_margins[-1]:
                    h_margins[-1] = max_right + right_margin - 1

        elif self._layout == 'row_major':
            # ---- Horizontal margins: independent per row ----
            n_rows = len(axes)
            for m, row_axes in enumerate(axes):
                row_h_margins = h_margins[m]
                right_edge = 0.0
                for n, ax in enumerate(row_axes):
                    br = self._bbox_rel(ax, m == n_rows - 1, n == 0, w, h, dpi)
                    left_edge = br[0] + sum(row_h_margins[:n+1])
                    x_delta = right_edge - left_edge + (inner_x_margin if n > 0 else left_margin)
                    if x_delta > 0:
                        row_h_margins[n] += x_delta
                    if br[0] + br[2] > 1 - right_margin + row_h_margins[-1]:
                        row_h_margins[-1] = br[0] + br[2] + right_margin - 1
                    right_edge = max(right_edge, br[0] + br[2] + sum(row_h_margins[:n+1]))

            # ---- Equalize left/right margins so all rows share the same outer edges ----
            shared_left = max(hm[0] for hm in h_margins)
            shared_right = max(hm[-1] for hm in h_margins)
            for hm in h_margins:
                hm[0] = shared_left
                hm[-1] = shared_right

            # ---- For rows with the same column count, equalize internal margins so
            #      column boundaries land at the same X positions across those rows ----
            from collections import defaultdict
            row_groups = defaultdict(list)
            for m, hm in enumerate(h_margins):
                row_groups[len(hm) - 1].append(m)  # key = number of columns
            for row_indices in row_groups.values():
                if len(row_indices) > 1:
                    n_internal = len(h_margins[row_indices[0]]) - 2
                    for k in range(1, n_internal + 1):
                        shared = max(h_margins[m][k] for m in row_indices)
                        for m in row_indices:
                            h_margins[m][k] = shared

            # ---- Vertical margins: shared across all rows ----
            bottom_edge = 1.0
            min_bottom = 1.0
            for m, row_axes in enumerate(axes):
                n_rows_total = len(axes)
                # tight bbox extent across all cols of this row
                max_top = max(
                    sum(self._bbox_rel(ax, m == n_rows_total - 1, n == 0, w, h, dpi)[1:4:2])
                    for n, ax in enumerate(row_axes)
                )
                min_bot = min(
                    self._bbox_rel(ax, m == n_rows_total - 1, n == 0, w, h, dpi)[1]
                    for n, ax in enumerate(row_axes)
                )
                top_edge = max_top - sum(v_margins[:m+1])
                y_delta = top_edge - bottom_edge + (inner_y_margin if m > 0 else top_margin)
                if y_delta > 0:
                    v_margins[m] += y_delta
                if min_bot + v_margins[-1] < 0:
                    v_margins[-1] = -min_bot
                min_bottom = min(min_bottom, min_bot - sum(v_margins[:m+1]))
                bottom_edge = min_bottom

        else:
            # regular
            n_rows = len(axes)
            max_right_edge = 0.0
            min_bottom_edge = 1.0
            bottom_edge = 1.0
            for m, row in enumerate(axes):
                right_edge = 0.0
                for n, ax in enumerate(row):
                    br = self._bbox_rel(ax, m == n_rows - 1, n == 0, w, h, dpi)
                    left_edge = br[0] + sum(h_margins[:n+1])
                    top_edge = br[1] + br[3] - sum(v_margins[:m+1])

                    x_delta = right_edge - left_edge + (inner_x_margin if n > 0 else left_margin)
                    y_delta = top_edge - bottom_edge + (inner_y_margin if m > 0 else top_margin)

                    if x_delta > 0:
                        h_margins[n] += x_delta
                    if y_delta > 0:
                        v_margins[m] += y_delta
                    right_edge = br[0] + br[2] + sum(h_margins[:n+1])
                    max_right_edge = max(right_edge, max_right_edge)
                    min_bottom_edge = min(min_bottom_edge, br[1] - sum(v_margins[:m+1]))

                    if br[0] + br[2] > 1 - right_margin + h_margins[-1]:
                        h_margins[-1] = br[0] + br[2] + right_margin - 1
                    if br[1] + v_margins[-1] < 0:
                        v_margins[-1] = -br[1]
                bottom_edge = min_bottom_edge

        return h_margins, v_margins
