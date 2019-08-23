# Plotly integration for the Moku:Lab Datalogger

# Copyright 2016 Liquid Instruments Pty. Ltd.

from pymoku import InvalidOperationException


def stream_init(moku, uname, api_key, str_id1,
                str_id2, npoints=100, mode='lines', line={}):

    line = ';'.join(['='.join(i) for i in list(line.items())])

    settings = [
        ('plotly.uname', uname),
        ('plotly.api_key', api_key),
        ('plotly.strid1', str_id1),
        ('plotly.strid2', str_id2),
        ('plotly.displaysize', str(npoints)),
        ('plotly.mode', mode),
        ('plotly.line', line),
    ]

    moku._set_properties(settings)


def stream_url(moku):
    return moku._get_property_single('plotly.url')


def plot_frame(dataframe, uname=None, api_key=None, mode='lines', line={}):
    try:
        import plotly.plotly as ply
        from plotly.graph_objs import Scatter, Layout, Data, Figure
    except ImportError:
        raise InvalidOperationException("Please install the Python "
                                        "plotly bindings")

    if uname and api_key:
        ply.sign_in(uname, api_key)

    c1 = dataframe.ch1
    c2 = dataframe.ch2
    x = list(range(len(c1)))

    t1 = Scatter(x=x, y=c1, mode=mode, line=line)
    t2 = Scatter(x=x, y=c2, mode=mode, line=line)

    layout = Layout(title="Moku:Lab Frame Grab")
    data = Data([t1, t2])

    fig = Figure(data=data, layout=layout)

    return ply.plot(fig)
