import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.axes import Axes
import numpy as np


class srAxes:
    """
    Presents an API that resembles the matplotlib "axis" API.
    However, nothing is actually drawn until "render" is called.
    Internally, we just a queue of commands for a real axis object
    """
    def __init__(self):
        self.f_queue = []
        self.args_queue = []
        self.kwargs_queue = []

    def set_xlim(self, *args, **kwargs):
        self.f_queue.append(Axes.set_xlim)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def set_ylim(self, *args, **kwargs):
        self.f_queue.append(Axes.set_ylim)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def plot(self, *args, **kwargs):
        self.f_queue.append(Axes.plot)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def set_xlabel(self, *args, **kwargs):
        self.f_queue.append(Axes.set_xlabel)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def set_ylabel(self, *args, **kwargs):
        self.f_queue.append(Axes.set_ylabel)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def set_xticklabels(self, *args, **kwargs):
        self.f_queue.append(Axes.set_xticklabels)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def set_yticklabels(self, *args, **kwargs):
        self.f_queue.append(Axes.set_yticklabels)
        self.args_queue.append(args)
        self.kwargs_queue.append(kwargs)

    def render(self, ax):
        for f, args, kwargs in zip(self.f_queue, self.args_queue, self.kwargs_queue):
            f(ax, *args, **kwargs)

class srFigure:

    def __init__(self, width=4, aspect_ratio=1, axis_label_size=12, panel_label_size=12, column_widths=[1.0,], row_heights=[1.0,], inner_margin_pt=6, rc_params=None):
        try:
            self.figure_width = width #inches
        except:
            self.set_figure_width(journal=width)
        
        self.panel_label_size = panel_label_size #pt
        self.axis_label_size = axis_label_size #pt
        self.aspect_ratio = aspect_ratio #h/w

        self.column_widths = column_widths / np.sum(column_widths)
        self.row_heights = row_heights / np.sum(row_heights)
        self.axes = np.array([[srAxes() for _ in column_widths] for _ in row_heights])
        self.inner_margin_pt = inner_margin_pt

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


    def render(self):
        """
        The workhorse.
        """
        #first render with no margins and figure out how much space we need to make
        h_margins = [0, ]*(len(self.column_widths)+1)
        v_margins = [0, ]*(len(self.row_heights)+1)
        with mpl.rc_context(self.rc_params):
            fig, axes = self.render_fixed_margins(h_margins, v_margins)
            h_margins, v_margins = self.correct_margins(fig, axes)
            plt.clf() #if working interactively, hide the "test" plot
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


    def correct_margins(self, fig, axes):


        w = self.figure_width
        h = self.aspect_ratio*self.figure_width
        inner_margin = (self.inner_margin_pt/72)/w

        h_margins = [0, ]*(len(self.column_widths)+1)
        v_margins = [0, ]*(len(self.row_heights)+1)

        real_column_widths = np.array(self.column_widths)*(1 -sum(h_margins))
        real_row_heights = np.array(self.row_heights)*(1 -sum(v_margins))


        Y = 1
        bottom_edge = 1.0
        for m, (row, srrow) in enumerate(zip(axes, self.axes)):
            right_edge = 0.0 
            for n, (ax, srax) in enumerate(zip(row, srrow)):

                bbox_pix = np.array(ax.axes.get_tightbbox().bounds)
                bbox_inches = bbox_pix / mpl.rcParams['figure.dpi']
                bbox_rel = [bbox_inches[0] / w, bbox_inches[1] / h,bbox_inches[2] / w, bbox_inches[3] / h]
                #panel_box_rel = [X,Y ,real_column_widths[n] , real_row_heights[m]]
                left_edge = bbox_rel[0] + sum([h_margins[i] for i in range(n+1)])
                top_edge= bbox_rel[1] +bbox_rel[3] - sum([v_margins[i] for i in range(m+1)])

                x_delta = (right_edge - left_edge)
                y_delta = (top_edge - bottom_edge)
                x_delta += n*inner_margin
                y_delta += m*inner_margin
                if x_delta > 0:
                    h_margins[n] += x_delta
                if y_delta > 0:
                    v_margins[m] += y_delta
                right_edge = bbox_rel[0] + bbox_rel[2] + sum([h_margins[i] for i in range(n+1)])
            if bbox_rel[0] + bbox_rel[2] > 1 + h_margins[-1]:
                h_margins[-1] = bbox_rel[0] + bbox_rel[2] - 1
            bottom_edge = bbox_rel[1] - sum([v_margins[i] for i in range(m+1)])
        if bbox_rel[1]  + v_margins[-1] <  0 :
            v_margins[-1] = -bbox_rel[1] 
        return h_margins, v_margins


    
