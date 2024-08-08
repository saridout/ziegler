Ziegler is a layer of convenience functions on top of matplotlib to suit my particular plotting preferences.

# Panel Layout
Many layout commands in matplotlib, e.g. ``fig.tight_layout()``, change the size of the figure. The primary goal of ziegler's layout algorithm, invoked by calling zfig.render(), is to achieve a tight layout without changing the specified figure dimensions.

To achieve a tighter or looser spacing of the panels, the Figure's ``inner_margin_pt`` variable, which specifies the margins between panels and the adjacent axis labels in points (1/72 of an inch) should be adjusted.

# Setting rc_params
Since realistically no one is going to use this library except me, Figure objects default to a set of rc_params that I personally prefer. To avoid this, you may pass ``rc_params={}`` to the constructor.

# Why the name?
There is much larger and more famous plotting library called "seaborn".
