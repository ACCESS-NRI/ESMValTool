#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
###############################################################################
flato13ipcc/fig9-42a.py
Author: Manuel Schlund (DLR, Germany)
CRESCENDO project
###############################################################################

Description
    Calculate and plot the equilibrium climate sensitivity (ECS) vs. the global
    mean surface temperature (GMSAT) for several CMIP5 models (see IPCC AR5 WG1
    ch. 9, fig. 9.42a).

Required diag_script_info attributes (diagnostics specific)
    [ecs_plots]
        plot : Switch to plot the linear regression needed for the ECS
               calculation
    [netcdf]
        filename  : Name of the output file
        overwrite : Overwrite existing files

Optional diag_script_info attributes (diagnostic specific)
    [main_plot]
        fontsize : Fonzsize used in the plot
        xmin     : Left boundary of the plot
        xmax     : Right boundary of the plot
        ymin     : Lower boundary of the plot
        ymax     : Upper boundary of the plot
    [ecs_plots]
        fontsize : Fontsize used in the plot
        xmin     : Left boundary of the plot
        xmax     : Right boundary of the plot
        ymin     : Lower boundary of the plot
        ymax     : Upper boundary of the plot

Caveats

Modification history
    20180522-A_schl_ma: ported to v2.0
    20171109-A_schl_ma: written

###############################################################################
"""


from esmvaltool.diag_scripts.shared import *

import iris

from collections import OrderedDict
import logging
import os

logger = logging.getLogger(os.path.basename(__file__))


def main(cfg):
    """
    Arguments
        cfg : Dictionary containing project information

    Description
        This is the main routine of the diagnostic.
    """

    ###########################################################################
    # Variables and experiments needed for this diagnostic
    ###########################################################################

    VARS = Variables(cfg)
    EXPS = Experiments(cfg)
    v1 = Variables(cfg, tas=Variable(1, 2, 3, 4))
    v2 = Variables(cfg, tas=Variable(1, 2, 3, [4, 5]))
    e1 = Experiments(cfg, 1)
    logging.info(VARS)
    logging.info(EXPS)
    logging.info(VARS.tas.exp)
    logging.info(VARS.short_names())
    logging.info(VARS.standard_names())
    logging.info(EXPS.names())

    # for filename, attributes in cfg['input_data'].items():
    #     logger.info("Processing variable %s from model %s",
    #                 attributes['standard_name'], attributes['model'])

    #     logger.debug("Loading %s", filename)
    #     cube = iris.load_cube(filename)

    #     logger.debug("Running example computation")
    #     cube = cube.collapsed('time', iris.analysis.MEAN)

    #     name = os.path.splitext(os.path.basename(filename))[0] + '_mean'
    #     if cfg['write_netcdf']:
    #         path = os.path.join(
    #             cfg['work_dir'],
    #             name + '.nc',
    #         )
    #         logger.debug("Saving analysis results to %s", path)
    #         iris.save(cube, target=path)

    #     if cfg['write_plots'] and cfg.get('quickplot'):
    #         path = os.path.join(
    #             cfg['plot_dir'],
    #             name + '.' + cfg['output_file_type'],
    #         )
    #         logger.debug("Plotting analysis results to %s", path)
    #         quickplot(cube, filename=path, **cfg['quickplot'])


if __name__ == '__main__':

    with run_diagnostic() as config:
        main(config)
