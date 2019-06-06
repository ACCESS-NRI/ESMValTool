"""APPLICATE/TRR Ocean Diagnostics."""
import itertools
import logging
import os
import pickle
from collections import OrderedDict

import cartopy.crs as ccrs
import matplotlib as mpl
from matplotlib import cm
import numpy as np

from esmvaltool.diag_scripts.ocean3d.getdata import (aw_core, hofm_data,
                                                     transect_data,
                                                     tsplot_data)
from esmvaltool.diag_scripts.ocean3d.plotting import (
    hofm_plot, plot2d_bias, plot2d_original_grid, plot_aw_core_stat,
    plot_profile, transect_map, transect_plot, tsplot_plot)
from esmvaltool.diag_scripts.ocean3d.utils import (find_observations_name,
                                                   get_clim_model_filenames,
                                                   get_cmap, get_fx_filenames,
                                                   timmean)
from esmvaltool.diag_scripts.shared import run_diagnostic

mpl.use('agg')  # noqa

logger = logging.getLogger(os.path.basename(__file__))


def main(cfg):
    """Compute the time average for each input model."""
    # for debuging save the configuration in a pickle file
    with open('cfg_NK.joblib', 'wb') as handle:
        pickle.dump(cfg, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # sets the directories
    diagworkdir = cfg['work_dir']
    diagplotdir = cfg['plot_dir']

    logger.info("Starting APPLICATE/TRR Arctic Ocean diagnostics")

    # find the name of the observational dataset
    observations = find_observations_name(cfg, 'thetao')
    logger.info("Name of the Observations: %s{}", observations)

    # get the names of fx filenames (for now are the same for
    # all variables (this is why "thetao" is hardcoded))
    areacello_fx = get_fx_filenames(cfg, 'thetao', 'areacello')
    logger.info("areacello_fx files: %s", areacello_fx)
    ########################################
    # Extract data for Hovmoeller diagrams
    ########################################
    # check if `hofm_data` flag is set
    if cfg['hofm_data']:
        logger.info("The `hofm_data` is True, going \
                     to extract monthly values for `hofm_regions`")

        logger.info("`hofm_vars` are: %s", cfg['hofm_vars'])
        # doing the loop for every variable
        for hofm_var in cfg['hofm_vars']:
            logger.info("Processing %s", hofm_var)
            # get dictionary with model names as key and path to the
            # preprocessed file as a value
            model_filenames = get_clim_model_filenames(cfg, hofm_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # loop over regions and models
            for mmodel, region in itertools.product(model_filenames,
                                                    cfg['hofm_regions']):
                # actual extraction of the data for specific model and region
                hofm_data(model_filenames, mmodel, hofm_var, areacello_fx,
                          cfg['hofm_depth'], region, diagworkdir)
    ############################################
    # Plot Hovmoeller diagrams for each variable
    ############################################
    # check if hofm_plot is set to True
    if cfg['hofm_plot']:
        # loop over variables
        for var_number, hofm_var in enumerate(cfg['hofm_vars']):
            # get dictionary with model names as key and path to the
            # preprocessed file as a value
            model_filenames = get_clim_model_filenames(cfg, hofm_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # set the color map if not default
            if cfg['hofm_cmap']:
                cmap = get_cmap(cfg['hofm_cmap'][var_number])
            else:
                cmap = get_cmap('Spectral_r')
            # set the number of columns in the output figure
            # if defined
            if cfg['hofm_ncol']:
                ncols = cfg['hofm_ncol']
            else:
                ncols = 3
            # get the levels for plots of this variable
            vmin, vmax, sstep, roundlimit = cfg['hofm_limits'][var_number]

            # loop over models and regions
            for mmodel, region in itertools.product(model_filenames,
                                                    cfg['hofm_regions']):
                logger.info("Plotting Model: %s for Region: %s, Variable %s",
                            mmodel, region, hofm_var)
                # actual plotting happens here
                hofm_plot(model_filenames,
                          hofm_var,
                          cfg['hofm_depth'],
                          region,
                          diagworkdir,
                          diagplotdir,
                          levels=np.round(np.linspace(vmin, vmax, sstep),
                                          roundlimit),
                          ncols=ncols,
                          cmap=cmap,
                          observations=observations)
    ########################################################
    # Create timemean (to be replaced by ESMValTool function)
    ########################################################

    if cfg['mean']:
        # loop over variables
        for hofm_var in cfg['hofm_vars']:
            model_filenames = get_clim_model_filenames(
                cfg,
                hofm_var,
            )
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # loop over models
            for model in model_filenames:
                timmean(model_filenames,
                        model,
                        hofm_var,
                        diagworkdir,
                        observations=observations)

    ############################################
    # plot average vertical profiles for regions
    ############################################
    if cfg['profiles']:
        # loop over variables
        for var_number, hofm_var in enumerate(cfg['hofm_vars']):
            model_filenames = get_clim_model_filenames(cfg, hofm_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # loop over regions
            for region in cfg['hofm_regions']:
                plot_profile(model_filenames,
                             hofm_var,
                             cfg['hofm_depth'],
                             region,
                             diagworkdir,
                             diagplotdir,
                             cmap=cm.Set2,
                             dpi=100,
                             observations=observations)
    ################################
    # Plot 2d maps on original grid
    ################################
    if cfg['plot2d']:
        # loop over variables
        for var_number, plot2d_var in enumerate(cfg['plot2d_vars']):
            model_filenames = get_clim_model_filenames(cfg, plot2d_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # set the color map
            if cfg['plot2d_cmap']:
                cmap = get_cmap(cfg['plot2d_cmap'][var_number])
            else:
                cmap = get_cmap('Spectral_r')
            # set the number of columns in the plot
            if cfg['plot2d_ncol']:
                ncols = cfg['plot2d_ncol']
            else:
                ncols = 3
            # create color limits for the plot
            vmin, vmax, sstep, roundlimit = cfg['plot2d_limits'][var_number]
            # loop over depths
            for depth in cfg['plot2d_depths']:
                plot2d_original_grid(model_filenames,
                                     plot2d_var,
                                     depth,
                                     levels=np.round(
                                         np.linspace(vmin, vmax, sstep),
                                         roundlimit),
                                     diagworkdir=diagworkdir,
                                     diagplotdir=diagplotdir,
                                     dpi=100)

    ###############################
    # plot model biases over depth
    ###############################
    if cfg['plot2d_bias']:
        # loop over variables
        for var_number, plot2d_bias_var in enumerate(cfg['plot2d_bias_vars']):

            model_filenames = get_clim_model_filenames(cfg, plot2d_bias_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # setup the color map
            if cfg['plot2d_bias_cmap']:
                cmap = get_cmap(cfg['plot2d_bias_cmap'][var_number])
            else:
                cmap = get_cmap('Spectral_r')
            # setup the number of columns
            if cfg['plot2d_bias_ncol']:
                ncols = cfg['plot2d_bias_ncol']
            else:
                ncols = 3
            # setup color limits
            vmin, vmax, sstep, roundlimit = cfg['plot2d_bias_limits'][
                var_number]
            # loop over depths
            for depth in cfg['plot2d_bias_depths']:
                plot2d_bias(model_filenames,
                            plot2d_bias_var,
                            depth,
                            diagworkdir,
                            diagplotdir,
                            levels=np.round(np.linspace(vmin, vmax, sstep),
                                            roundlimit),
                            dpi=100,
                            observations=observations)
    #################
    # plot transects
    #################
    if cfg['transects']:
        # First plot the map woth transect points for each "region"
        for region in cfg['transects_regions']:
            transect_map(region,
                         diagplotdir,
                         projection=ccrs.NorthPolarStereo(),
                         bbox=[-180, 180, 60, 90],
                         mult=2)
        # loop over variables
        for var_number, trans_var in enumerate(cfg['transects_vars']):
            model_filenames = get_clim_model_filenames(cfg, trans_var)
            model_filenames = OrderedDict(
                sorted(model_filenames.items(), key=lambda t: t[0]))
            # loop over regions
            for mmodel, region in itertools.product(model_filenames,
                                                    cfg['transects_regions']):
                # ploting a transect
                transect_data(mmodel, trans_var, region, diagworkdir)
            # setup a color map
            if cfg['transects_cmap']:
                cmap = get_cmap(cfg['transects_cmap'][var_number])
            else:
                cmap = get_cmap('Spectral_r')
            # setup number of columns
            if cfg['transects_ncol']:
                ncols = cfg['transects_ncol']
            else:
                ncols = 3
            # setup color limits
            vmin, vmax, sstep, roundlimit = cfg['transects_limits'][var_number]
            # loop over regions
            for region in cfg['transects_regions']:
                transect_plot(model_filenames,
                              trans_var,
                              cfg['transects_depth'],
                              region,
                              diagworkdir,
                              diagplotdir,
                              levels=np.round(np.linspace(vmin, vmax, sstep),
                                              roundlimit),
                              ncols=ncols,
                              cmap=cmap)

    ############################################################
    # Calculate depth and temperature of the Atlantic Water core
    # and make plots.
    ############################################################
    if cfg['AW_core']:
        model_filenames = get_clim_model_filenames(cfg, 'thetao')
        model_filenames = OrderedDict(
            sorted(model_filenames.items(), key=lambda t: t[0]))
        aw_core_parameters = aw_core(model_filenames, diagworkdir, 'EB',
                                     'thetao')
        plot_aw_core_stat(aw_core_parameters, diagplotdir)

    ###########################################################
    # Plot temperature spatial distribution at the depth of the
    # atlantic water core in different models
    ###########################################################
    if cfg['AW_core_2d']:
        model_filenames = get_clim_model_filenames(cfg, 'thetao')
        model_filenames = OrderedDict(
            sorted(model_filenames.items(), key=lambda t: t[0]))
        aw_core_parameters = aw_core(model_filenames, diagworkdir, 'EB',
                                     'thetao')
        # this is now just using plot2d_original_grid with
        # additional `explicit_depths` parameter
        plot2d_original_grid(
            model_filenames,
            cmor_var="thetao",
            depth=0,
            levels=np.round(np.linspace(-2, 2.3, 41), 1),
            diagworkdir=diagworkdir,
            diagplotdir=diagplotdir,
            dpi=100,
            explicit_depths=aw_core_parameters,
        )

    #############################
    # plot TS diagrams
    #############################
    if cfg['tsdiag']:
        # get the dictionary with model file names
        model_filenames = get_clim_model_filenames(cfg, 'thetao')
        model_filenames = OrderedDict(
            sorted(model_filenames.items(), key=lambda t: t[0]))
        # loop over models and regions
        for mmodel, region in itertools.product(model_filenames,
                                                cfg['tsdiag_regions']):
            # this function will generate files with T and S points
            # selected from the region untill `tsdiag_depth` for
            # every model.
            tsplot_data(mmodel,
                        cfg['tsdiag_depth'],
                        region,
                        diagworkdir,
                        observations=observations)
        # setting the number of columns for the plot
        if cfg['tsdiag_ncol']:
            ncols = cfg['tsdiag_ncol']
        else:
            ncols = 3
        # actually plot TS diagrams
        for region in cfg['tsdiag_regions']:
            tsplot_plot(model_filenames,
                        cfg['tsdiag_depth'],
                        region,
                        diagworkdir,
                        diagplotdir,
                        ncols=ncols,
                        cmap=cm.Set1,
                        observations=observations)


if __name__ == '__main__':

    with run_diagnostic() as config:
        main(config)
