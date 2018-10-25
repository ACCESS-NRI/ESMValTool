"""Derivation of variable `netcre`."""


from ._derived_variable_base import DerivedVariableBase
from .lwcre import DerivedVariable as Lwcre
from .swcre import DerivedVariable as Swcre


class DerivedVariable(DerivedVariableBase):
    """Derivation of variable `netcre`."""

    def get_required(self, frequency):
        """Get variable `short_name` and `field` pairs required for derivation.

        Parameters
        ----------
        frequency : str
            Frequency of the desired derived variable.

        Returns
        -------
        list of tuples
            List of tuples (`short_name`, `field`) of all variables required
            for derivation.

        """
        return [('rlut', 'T2' + frequency + 's'),
                ('rlutcs', 'T2' + frequency + 's'),
                ('rsut', 'T2' + frequency + 's'),
                ('rsutcs', 'T2' + frequency + 's')]

    def calculate(self, cubes, fx_files=None):
        """Compute net cloud radiative effect.

        Calculate net cloud radiative effect as sum of longwave and shortwave
        cloud radiative effects.

        Parameters
        ----------
        cubes : iris.cube.CubeList
            `CubeList` containing `rlut` (`toa_outgoing_longwave_flux`),
            `rlutcs` (`toa_outgoing_longwave_flux_assuming_clear_sky`),
            `rsut` (`toa_outgoing_shortwave_flux`) and `rsutcs`
            (`toa_outgoing_shortwave_flux_assuming_clear_sky`).
        fx_files : dict, optional
            If required, dictionary containing fx files  with `short_name`
            (key) and path (value) of the fx variable.

        Returns
        -------
        iris.cube.Cube
            `Cube` containing net cloud radiative effect.

        """
        lwcre_var = Lwcre()
        swcre_var = Swcre()
        lwcre_cube = lwcre_var.calculate(cubes)
        swcre_cube = swcre_var.calculate(cubes)

        netcre_cube = lwcre_cube + swcre_cube
        netcre_cube.units = lwcre_cube.units

        return netcre_cube
