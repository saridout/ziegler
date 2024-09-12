import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.axes import Axes as mAxes
import numpy as np

import inspect

class Axes:
    """
    Presents an API that resembles the matplotlib "axis" API.
    However, nothing is actually drawn until "render" is called.
    Internally, we just a queue of commands for a real axis object
    """

    def __init__(self, axis_label_fontsize=12):
        self.f_queue = []
        self.args_queue = []
        self.kwargs_queue = []
        self.axis_label_fontsize=axis_label_fontsize

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



    def render(self, ax):
        for f, args, kwargs in zip(self.f_queue, self.args_queue, self.kwargs_queue):
            f(ax, *args, **kwargs)
        for g, args, _kwargs in zip(self.plt_f_queue, self.plt_args_queue, self.plt_kwargs_queue):
            kwargs = {}
            for key in _kwargs:
                if _kwargs[key] == self:
                    kwargs[key] = ax
                else:
                    kwargs[key] = _kwargs[key]

            g(*args, **kwargs)

class Figure:

    def __init__(self, width=4, aspect_ratio=1, axis_label_fontsize=12, panel_label_fontsize=12, column_widths=[1.0,], row_heights=[1.0,], inner_margin_pt=6, top_margin_pt=0, left_margin_pt=0, rc_params=None):
        try:
            self.figure_width = float(width) #inches
        except: 
            self.set_figure_width(journal=width)
        
        self.panel_label_fontsize = panel_label_fontsize #pt
        self.aspect_ratio = aspect_ratio #h/w

        self.column_widths = column_widths / np.sum(column_widths)
        self.row_heights = row_heights / np.sum(row_heights)
        self.axes = np.array([[Axes(axis_label_fontsize=axis_label_fontsize) for _ in column_widths] for _ in row_heights])
        self.inner_margin_pt = inner_margin_pt
        self.top_margin_pt = top_margin_pt
        self.left_margin_pt = left_margin_pt

        if rc_params == None:
            self.rc_params = {"xtick.direction": 'in', "ytick.direction": 'in' }
        else:
            self.rc_params = {}

    def set_figure_width(self, width_inches=None, journal=None):
        if not width_inches == None:
            self.figure_width = width_inches
        else:
            if journal == "PR":
                self.figure_width = 3 + 3/8
            if journal == "eLife":
                self.figure_width = 5.6
            if journal == "PR_full":
                self.figure_width = 7.08
            if journal == "AnnRev": #strictly speaking, Annual Review of Condensed Matter Physics. may be different for others, not sure
                self.figure_width = 5.06


    def render(self):
        """
        The workhorse.
        """
        #first render with no margins and figure out how much space we need to make
        h_margins = [0, ]*(len(self.column_widths)+1)
        v_margins = [0, ]*(len(self.row_heights)+1)
        with mpl.rc_context(self.rc_params):
            fig, axes = self.render_fixed_margins(h_margins, v_margins)
            h_margins, v_margins = self.correct_margins(fig, axes, h_margins, v_margins)
            plt.clf() #if working interactively, hide the "test" plot
            fig, axes = self.render_fixed_margins(h_margins, v_margins)
            #need to correct a second time to approximately fix a higher-order correction my formula doesn't account for
            #this correction arises if the stuff sticking into the margins is the tick labels rather than the axis labels
            #One day, I will try to figure out how to apply the exact correction instead
            h_margins, v_margins = self.correct_margins(fig, axes, h_margins, v_margins) 
            plt.clf()
            fig, axes = self.render_fixed_margins(h_margins, v_margins)

        return fig, axes


    def render_fixed_margins(self, h_margins, v_margins):
        
        w = self.figure_width
        h = self.aspect_ratio*self.figure_width
        
        fig = plt.figure(figsize=(w, h))

        real_column_widths = np.array(self.column_widths)*(1 -sum(h_margins))
        real_row_heights = np.array(self.row_heights)*(1 -sum(v_margins))
        
        axes = []
        Y = 1
        for m, row in enumerate(self.axes):
            axes.append([])
            Y = Y - v_margins[m]
            Y = Y - real_row_heights[m]
            X = 0
            for n, srax in enumerate(row):
                X = X + h_margins[n]
                ax = fig.add_axes([X,Y ,real_column_widths[n] , real_row_heights[m]])
                X = X + real_column_widths[n]

                srax.render(ax)
                axes[-1].append(ax)
                bbox_pix = np.array(ax.axes.get_tightbbox().bounds)
                bbox_inches = bbox_pix / mpl.rcParams['figure.dpi']
                bbox_rel = [bbox_inches[0] / w, bbox_inches[1] / h,bbox_inches[2] / w, bbox_inches[3] / h]


        return fig, axes


    def correct_margins(self, fig, axes, h_margins, v_margins):


        w = self.figure_width
        h = self.aspect_ratio*self.figure_width
        inner_x_margin = (self.inner_margin_pt/72)/w
        inner_y_margin = (self.inner_margin_pt/72)/h
        left_margin = (self.left_margin_pt/72)/w
        top_margin = (self.top_margin_pt/72)/h


        real_column_widths = np.array(self.column_widths)*(1 -sum(h_margins))
        real_row_heights = np.array(self.row_heights)*(1 -sum(v_margins))


        Y = 1
        max_right_edge = 0.0
        min_bottom_edge = 1.0
        bottom_edge = 1.0
        for m, (row, srrow) in enumerate(zip(axes, self.axes)):
            right_edge = 0.0 
            for n, (ax, srax) in enumerate(zip(row, srrow)):

                bbox_pix = np.array(ax.axes.get_tightbbox().bounds)
                bbox_inches = bbox_pix / mpl.rcParams['figure.dpi']
                bbox_rel = [bbox_inches[0] / w, bbox_inches[1] / h,bbox_inches[2] / w, bbox_inches[3] / h]
                left_edge = bbox_rel[0] + sum([h_margins[i] for i in range(n+1)])
                top_edge= bbox_rel[1] +bbox_rel[3] - sum([v_margins[i] for i in range(m+1)])

                x_delta = (right_edge - left_edge)
                y_delta = (top_edge - bottom_edge)
                if n > 0:
                    x_delta += inner_x_margin
                else:
                    x_delta += left_margin
                if m > 0:
                    y_delta += inner_y_margin
                else:
                    y_delta += top_margin

                if x_delta > 0:
                    h_margins[n] += x_delta
                if y_delta > 0:
                    v_margins[m] += y_delta
                right_edge = bbox_rel[0] + bbox_rel[2] + sum([h_margins[i] for i in range(n+1)])
                max_right_edge = max(right_edge, max_right_edge)
                min_bottom_edge = min(min_bottom_edge, bbox_rel[1] - sum([v_margins[i] for i in range(m+1)]))

                if bbox_rel[0] + bbox_rel[2] > 1 + h_margins[-1]:
                    h_margins[-1] = bbox_rel[0] + bbox_rel[2] - 1
                if bbox_rel[1]  + v_margins[-1] <  0 :
                    v_margins[-1] = -bbox_rel[1] 
            bottom_edge = min_bottom_edge

        return h_margins, v_margins


    
