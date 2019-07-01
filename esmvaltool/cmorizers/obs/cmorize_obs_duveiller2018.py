# pylint: disable=invalid-name
"""ESMValTool CMORizer for Duveiller2018 data.

Tier
   Tier 2: other freely-available dataset.

Source
   https://www.nature.com/articles/sdata201814

Last access
   20190430

Download and processing instructions
   - Download the dataset albedo_IGBPgen.nc and save in the right directory
     according to ESMValTool practices.
   - Complete the CMOR-config specifications (see instructions in the file
     itself)
   - Run cmorize_obs

Modification history
   20190701-A_crez_ba: submitted PR
   20190430-A_crez_ba: started with cmorize_obs_Landschuetzer2016.py as an
   example to follow

Caveats
   Please be aware that the selected vegetation transition code is not written
   to the filename, since this would break the ESMValTool file naming
   conventions.
"""

import datetime
import logging
import os
from warnings import catch_warnings, filterwarnings

import cf_units
import iris
import numpy as np
from dask import array as da

from .utilities import (fix_coords, fix_var_metadata, save_variable,
                        set_global_atts)

logger = logging.getLogger(__name__)


def fix_time_coord_duveiller2018(cube):
    """Fix the time coordinate for dataset Duveiller2018."""
    # Rename 'Month' to 'time'
    cube.coord('Month').rename('time')

    # Create arrays for storing datetime objects
    custom_time = np.zeros((12), dtype=object)
    custom_time_bounds = np.empty((12, 2), dtype=object)
    custom_time_units = 'days since 1950-01-01'

    # Now fill the object arrays defined above with datetime objects
    # corresponding to correct time and time_bnds
    for i in range(custom_time_bounds.shape[0]):
        n_month = i + 1  # we start with month number 1, at position 0
        # Start with time_bnds
        time_bnd_a = datetime.datetime(2010, n_month, 1)
        if n_month == 12:
            time_bnd_b = datetime.datetime(2011, 1, 1)
        else:
            time_bnd_b = datetime.datetime(2010, n_month + 1, 1)
        # Get time 'point' from midpoint between bnd_a and bnd_b
        time_midpoint = time_bnd_a + 0.5 * (time_bnd_b - time_bnd_a)
        custom_time_bounds[n_month - 1, 0] = time_bnd_a
        custom_time_bounds[n_month - 1, 1] = time_bnd_b
        custom_time[n_month - 1] = time_midpoint

    # Convert them
    time_bnds = cf_units.date2num(custom_time_bounds, custom_time_units,
                                  cf_units.CALENDAR_GREGORIAN)
    time_midpoints = cf_units.date2num(custom_time, custom_time_units,
                                       cf_units.CALENDAR_GREGORIAN)

    # Add them to the cube
    cube.coord('time').bounds = time_bnds
    cube.coord('time').points = time_midpoints

    # Set the correct time unit, as defined above
    cube.coord('time').units = cf_units.Unit(custom_time_units)


def extract_variable(var_info, raw_info, out_dir, attrs, cfg):
    """Extract to all vars."""
    var = var_info.short_name
    with catch_warnings():
        filterwarnings(
            action='ignore',
            message='Ignoring netCDF variable .* invalid units .*',
            category=UserWarning,
            module='iris',
        )
        cubes = iris.load(raw_info['file'])
    rawvar = raw_info['name']
    for cube in cubes:
        if cube.var_name == rawvar:
            # Extracting a certain vegetation transition code
            # Read iTr parameter from the cfg
            itr = cfg['parameters']['iTr']
            itr_index = np.where(
                cube.coords('Vegetation transition code')[0].points ==
                itr)[0][0]
            cube = cube[itr_index, :, :, :]
            # Add the vegetation transition code as an attribute
            cube.attributes['Vegetation transition code'] = itr
            # Remove it as a coordinate, since otherwise it would
            # violate CMOR standards
            cube.remove_coord('Vegetation transition code')
            # Fix metadata
            fix_var_metadata(cube, var_info)
            # Fix coords
            fix_coords(cube)
            # Now set the time coordinate properly
            fix_time_coord_duveiller2018(cube)
            # Latitude has to be increasing so flip it
            # (this is not fixed in fix_coords)
            coord_name = 'latitude'
            logger.info("Flipping dimensional coordinate (custom) %s...",
                        coord_name)
            coord = cube.coord(coord_name, dim_coords=True)
            coord_idx = cube.coord_dims(coord)[0]
            coord.points = np.flip(coord.points)
            coord.bounds = np.flip(coord.bounds, axis=0)
            coord.bounds = np.flip(coord.bounds, axis=1)
            cube.data = da.flip(cube.core_data(), axis=coord_idx)
            # Global attributes
            set_global_atts(cube, attrs)
            save_variable(cube, var, out_dir, attrs, local_keys=['positive'])


def cmorization(in_dir, out_dir, cfg):
    """Cmorization func call."""
    cmor_table = cfg['cmor_table']
    glob_attrs = cfg['attributes']

    logger.info("Starting cmorization for Tier%s OBS files: %s",
                glob_attrs['tier'], glob_attrs['dataset_id'])
    logger.info("Input data from: %s", in_dir)
    logger.info("Output will be written to: %s", out_dir)

    # run the cmorization
    for var, vals in cfg['variables'].items():
        inpfile = os.path.join(in_dir, vals['file'])
        logger.info("CMORizing var %s from file %s", var, inpfile)
        var_info = cmor_table.get_variable(vals['mip'], var)
        print("var = ", var)
        raw_info = {'name': vals['raw'], 'file': inpfile}
        glob_attrs['mip'] = vals['mip']
        with catch_warnings():
            filterwarnings(
                action='ignore',
                message=('WARNING: missing_value not used since it\n'
                         'cannot be safely cast to variable data type'),
                category=UserWarning,
                module='iris',
            )
            extract_variable(var_info, raw_info, out_dir, glob_attrs, cfg)
