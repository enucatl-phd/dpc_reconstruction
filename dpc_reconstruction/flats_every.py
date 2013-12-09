"""
If the scan has many flats, separate the various chunks and analyse then one
by one.

"""
from __future__ import division, print_function

import logging
import numpy as np

import pypes.component
import pypesvds.lib.packet

log = logging.getLogger(__name__)


def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    http://stackoverflow.com/a/312464
    """
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


class SplitFlatSampleEvery(pypes.component.Component):
    """
    mandatory input packet attributes:
    - None (only receives a trigger but the data is set up on
      initialization)

    optional input packet attributes:
    - None

    parameters:
    - flats_every: every how many files is a flat scan taken?
    - n_flats: n consecutive flats to average
    - files: list with all the files

    output packet attributes:
    - many output ports: each group of files (with one flat) is sent to an
      output.
    - for each output port: (matches the SplitFlatSample interface)
        - sample: list with the files for the sample
        - flat: list with the files for the flats

    """

    # defines the type of component we're creating.
    __metatype__ = 'ADAPTER'

    def __init__(self, files, flats_every,
                 n_flats):
        # initialize parent class
        pypes.component.Component.__init__(self)

        self.set_parameter("flats_every", flats_every)
        self.set_parameter("n_flats", n_flats)
        self.set_parameter("files", files)

        n = len(files) // (flats_every + n_flats)

        # Optionally add/remove component ports
        self.remove_output('out')
        for i in range(n):
            self.add_output('out{0}'.format(i))

        # log successful initialization message
        log.debug('Component Initialized: %s', self.__class__.__name__)

    def run(self):
        # Define our components entry point
        while True:

            # receives only a trigger
            _ = self.receive('in')
            try:
                files = self.get_parameter("files")
                flats_every = self.get_parameter("flats_every")
                n_flats = self.get_parameter("n_flats")
                n = flats_every + n_flats
                for i, chunk in enumerate(chunks, files, n):
                    sample = chunk[:flats_every]
                    flat = chunks[flats_every:flats_every + n_flats]
                    packet = pypesvds.lib.packet.Packet()
                    packet.set("sample", sample)
                    packet.set("flat", flat)
                    log.debug("%s: created sample dataset with shape %s",
                              self.__class__.__name__, sample.shape)
                    log.debug("%s: created flat dataset with shape %s",
                              self.__class__.__name__, flat.shape)
                    port = "out{0}".format(i)
                    self.send(port, packet)
            except:
                log.error('Component Failed: %s',
                          self.__class__.__name__, exc_info=True)

            # yield the CPU, allowing another component to run
            self.yield_ctrl()


class MergeFlatsEvery(pypes.component.Component):
    """
    mandatory input packet attributes:
    for each input port:
    - data: a dataset with the fully analyzed chunk

    optional input packet attributes:
    - None

    parameters:
    - n: number of inputs
    - full_path: full path of the HDF5 to be used as output

    output packet attributes:
    - data: a merge of all the input datasets.
    - full_path: path to be used for saving to an HDF5 file

    """

    # defines the type of component we're creating.
    __metatype__ = 'TRANSFORMER'

    def __init__(self, n):
        # initialize parent class
        pypes.component.Component.__init__(self)

        self.set_parameter("n", n)
        self.set_parameter("full_path", None)

        self.remove_input('in')
        for i in range(n):
            self.add_output('in{0}'.format(i))

        # log successful initialization message
        log.debug('Component Initialized: %s', self.__class__.__name__)

    def run(self):
        # Define our components entry point
        while True:

            # for each packet waiting on our input port
            n = self.get_parameter("n")
            datasets = []
            for i in range(n):
                packet = self.receive("in{0}".format(i))
                if not packet:
                    log.error("%d packet is None!", i)
                    continue
                try:
                    data = packet.get("data")
                    datasets.append(data)
                except:
                    log.error('Component Failed: %s',
                              self.__class__.__name__, exc_info=True)

            dataset = np.dstack(datasets)
            packet = pypesvds.lib.packet.Packet()
            packet.set("data", dataset)
            packet.set("full_path",
                       self.get_parameter("full_path"))
            log.debug("%s: created dataset with shape %s",
                      self.__class__.__name__, dataset.shape)
            # send the packet to the next component
            self.send('out', packet)

            # yield the CPU, allowing another component to run
            self.yield_ctrl()
