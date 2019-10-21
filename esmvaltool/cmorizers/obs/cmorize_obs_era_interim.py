"""ESMValToo CMORizer for ERA-Interim data.

Tier
    Tier 3: restricted datasets (i.e., dataset which requires a registration
 to be retrieved or provided upon request to the respective contact or PI).

Source
    http://apps.ecmwf.int/datasets/data/interim-full-moda/

Last access
    20190905

Download and processing instructions
    Select "ERA Interim Fields":
        Daily: for daily values
        Invariant: for time invariant variables (like land-sea mask)
        Monthly Means of Daily Means: for monthly values
        Monthly Means of Daily Forecast Accumulation: for accumulated variables
        like precipitation or radiation fluxes
    Select "Type of level" (Surface or Pressure levels)
    Download the data on a single variable and single year basis, and save
    them as ERA-Interim_<var>_<mean>_YYYY.nc, where <var> is the ERA-Interim
    variable name and <mean> is either monthly or daily. Further download
    "land-sea mask" from the "Invariant" data and save it in
    ERA-Interim_lsm.nc.
    It is also possible to download data in an automated way, see:
        https://confluence.ecmwf.int/display/WEBAPI/Access+ECMWF+Public+Datasets
        https://confluence.ecmwf.int/display/WEBAPI/Python+ERA-interim+examples
    A registration is required for downloading the data.
    It is alo possible to use the script in:
    esmvaltool/cmorizers/obs/download_scripts/download_era-interim.py
    This cmorization script currently supports daily and monthly data of
the following variables:
        10m u component of wind
        10m v component of wind
        2m dewpoint temperature
        2m temperature
        evaporation
        maximum 2m temperature since previous post processing
        mean sea level pressure
        minimum 2m temperature since previous post processing
        skin temperature
        snowfall
        surface net solar radiation
        surface solar radiation downwards
        temperature of snow layer
        toa incident solar radiation
        total cloud cover
        total precipitation
and daily, monthly (not invariant) data of:
        Geopotential

and monthly data of:
        Inst. eastward turbulent surface stress
        Inst. northward turbulent surface stress
        Sea surface temperature
        Surface net thermal radiation
        Surface latent heat flux
        Surface sensible heat flux
        Relative humidity
        Temperature
        U component of wind
        V component of wind
        Vertical velocity
        Specific humidity

Caveats
    Make sure to select the right steps for accumulated fluxes, see:
        https://confluence.ecmwf.int/pages/viewpage.action?pageId=56658233
        https://confluence.ecmwf.int/display/CKB/ERA-Interim%3A+monthly+means
    for a detailed explanation.
    The data are updated regularly: recent years are added, but also the past
    years are sometimes corrected. To have a consistent timeseries, it is
    therefore recommended to download the full timeseries and not just add
    new years to a previous version of the data.

"""
from datetime import datetime, timedelta
import logging
from concurrent.futures import as_completed, ProcessPoolExecutor
from copy import deepcopy
from os import cpu_count
from pathlib import Path
from warnings import catch_warnings, filterwarnings
from collections import defaultdict

import iris
import numpy as np

from esmvalcore.cmor.table import CMOR_TABLES
from esmvalcore.preprocessor import daily_statistics
from . import utilities as utils

logger = logging.getLogger(__name__)


def _set_global_attributes(cube, attributes, definition):
    """Set global attributes"""
    utils.set_global_atts(cube, attributes)
    # Here var_name is the raw era-interim name
    if cube.var_name in {'e', 'sf'}:
        # Change evaporation and snowfall units from
        # 'm of water equivalent' to m
        cube.units = 'm'
    if cube.var_name in {'e', 'sf', 'tp', 'pev'}:
        # Change units from meters per day of water to kg of water per day
        cube.units = cube.units * 'kg m-3 day-1'
        cube.data = cube.core_data() * 1000.
    if cube.var_name in {'ssr', 'ssrd', 'tisr', 'hfds'}:
        # Add missing 'per day'
        cube.units = cube.units * 'day-1'
        # Radiation fluxes are positive in downward direction
        cube.attributes['positive'] = 'down'
    if cube.var_name in {'iews', 'inss'}:
        cube.attributes['positive'] = 'down'
    if cube.var_name in {'lsm', 'tcc'}:
        # Change units from fraction to percentage
        cube.units = definition.units
        cube.data = cube.core_data() * 100.
    if cube.var_name in {'z'}:
        # Divide by acceleration of gravity [m s-2],
        # required for surface geopotential height, see:
        # https://confluence.ecmwf.int/pages/viewpage.action?pageId=79955800
        cube.units = cube.units / 'm s-2'
        cube.data = cube.core_data() / 9.80665


def _fix_coordinates(cube, definition):
    # Fix coordinates
    # Make latitude increasing
    cube = cube[:, ::-1, ...]
    # Add height coordinate
    if 'height2m' in definition.dimensions:
        utils.add_scalar_height_coord(cube, 2.)
    if 'height10m' in definition.dimensions:
        utils.add_scalar_height_coord(cube, 10.)
    for axis in 'T', 'X', 'Y', 'Z':
        coord_def = definition.coordinates.get(axis)
        if coord_def:
            coord = cube.coord(axis=axis)
            if axis == 'T':
                coord.convert_units('days since 1850-1-1 00:00:00.0')
            if axis == 'Z':
                coord.convert_units(coord_def.units)
            coord.standard_name = coord_def.standard_name
            coord.var_name = coord_def.out_name
            coord.long_name = coord_def.long_name
            coord.points = coord.core_points().astype('float64')
            if len(coord.points) > 1:
                coord.guess_bounds()


def _fix_frequency(cube, var):
    # Here var_name is the CMIP name
    # era-interim is in 3hr or 6hr or 12hr freq need to convert to daily
    # only variables with step 12 need accounting time 00 AM as time 24 PM
    if var['mip'] in {'day', 'Eday', 'CFday'}:
        # accounting time 00 AM as time 24 PM
        if cube.var_name in {'tasmax', 'tasmin', 'pr',
                             'rsds', 'hfds', 'evspsbl',
                             'rsdt', 'rss', 'prsn'}:
            cube.coord('time').points = [
                cube.coord('time').units.date2num(
                    cell.point - timedelta(seconds=1)
                )
                for cell in cube.coord('time').cells()
            ]
        if cube.var_name == 'tasmax':
            cube = daily_statistics(cube, 'max')
        elif cube.var_name == 'tasmin':
            cube = daily_statistics(cube, 'min')
        elif cube.var_name in {'pr', 'rsds', 'hfds', 'evspsbl',
                               'rsdt', 'rss', 'prsn'}:
            cube = daily_statistics(cube, 'sum')
        else:
            cube = daily_statistics(cube, 'mean')
        # Remove daily statistics helpers
        cube.remove_coord(cube.coord('day_of_year'))
        cube.remove_coord(cube.coord('year'))
        # Correct the time bound
        cube.coord('time').points = cube.coord('time').units.date2num(
            [
                cell.point.replace(hour=12, minute=0, second=0,
                                   microsecond=0)
                for cell in cube.coord('time').cells()
            ]
        )
        cube.coord('time').bounds = None
        cube.coord('time').guess_bounds()
    return cube


def _get_files(in_dir, var):
    # Make a dictionary with the keys that are years
    files_dict = defaultdict(list)
    for in_file in var['files']:
        files_lst = sorted(list(Path(in_dir).glob(in_file)))
        for item in files_lst:
            year = str(item.stem).split('_')[-1]
            files_dict[year].append(item)
    # Check if files are complete
    for year in files_dict.copy():
        if len(files_dict[year]) != len(var['files']):
            logger.info("CMORizing %s at time '%s' needs '%s' input file/s",
                        var['short_name'], year, len(var['files']))
            files_dict.pop(year)
    return files_dict


def _extract_variable(in_file, var, cfg, out_dir):
    if 'files' in var:
        logger.info("CMORizing variable '%s' from input file/s '%s'",
                    var['short_name'], [str(item) for item in in_file])
    else:
        logger.info("CMORizing variable '%s' from input file/s '%s'",
                    var['short_name'], in_file)
    attributes = deepcopy(cfg['attributes'])
    attributes['mip'] = var['mip']
    cmor_table = CMOR_TABLES[attributes['project_id']]
    definition = cmor_table.get_variable(var['mip'], var['short_name'])

    with catch_warnings():
        filterwarnings(
            action='ignore',
            message="Ignoring netCDF variable 'tcc' invalid units '(0 - 1)'",
            category=UserWarning,
            module='iris',
        )
        filterwarnings(
            action='ignore',
            message="Ignoring netCDF variable 'lsm' invalid units '(0 - 1)'",
            category=UserWarning,
            module='iris',
        )
        filterwarnings(
            action='ignore',
            message=("Ignoring netCDF variable 'e' invalid units "
                     "'m of water equivalent'"),
            category=UserWarning,
            module='iris',
        )
        if 'files' in var:
            if var['operator'] == 'sum':
                # Multiple variables case using sum operation
                for i, item in enumerate(in_file):
                    in_cube = iris.load_cube(
                        str(item),
                        constraint=utils.var_name_constraint(var['raw'][i]),
                    )
                    if i == 0:
                        cube = in_cube
                    else:
                        cube += in_cube
                cube.var_name = var['short_name']
        else:
            cube = iris.load_cube(
                str(in_file),
                constraint=utils.var_name_constraint(var['raw']),
            )

    _set_global_attributes(cube, attributes, definition)

    # Set correct names
    cube.var_name = definition.short_name
    cube.standard_name = definition.standard_name
    cube.long_name = definition.long_name

    # Fix data type
    cube.data = cube.core_data().astype('float32')

    _fix_coordinates(cube, definition)
    cube = _fix_frequency(cube, var)

    # Convert units if required
    cube.convert_units(definition.units)

    logger.info("Saving cube\n%s", cube)
    logger.info("Expected output size is %.1fGB",
                np.prod(cube.shape) * 4 / 2 ** 30)
    utils.save_variable(
        cube,
        cube.var_name,
        out_dir,
        attributes,
        local_keys=['positive'],
    )


def cmorization(in_dir, out_dir, cfg, _):
    """Cmorization func call."""
    cfg['attributes']['comment'] = cfg['attributes']['comment'].format(
        year=datetime.now().year)
    cfg.pop('cmor_table')

    n_workers = int(cpu_count() / 1.5)
    logger.info("Using at most %s workers", n_workers)
    futures = {}
    with ProcessPoolExecutor(max_workers=1) as executor:
        for short_name, var in cfg['variables'].items():
            if 'short_name' not in var:
                var['short_name'] = short_name
            if 'file' in var:
                for in_file in sorted(Path(in_dir).glob(var['file'])):
                    future = executor.submit(_extract_variable, in_file,
                                             var, cfg, out_dir)
                    futures[future] = in_file
            if 'files' in var:
                # Multiple variables case
                files_dict = _get_files(in_dir, var)
                for key in files_dict:
                    in_file = files_dict[key]
                    future = executor.submit(_extract_variable, in_file,
                                             var, cfg, out_dir)
                    futures[future] = [str(item) for item in in_file]

    for future in as_completed(futures):
        try:
            future.result()
        except:  # noqa
            logger.error("Failed to CMORize %s", futures[future])
            raise
        logger.info("Finished CMORizing %s", futures[future])
