# GTSM reanalysis processing scripts for BlueEarth Data

Creator: Daniel Twigt
Date: 24-06-2020

- Background info to GTSM reanalysis processing prior to ingestion into BlueEarth Data
- Uses DIVAnd as obtained from https://github.com/gher-ulg/DIVAnd.jl

## gtsm_interpolate_tide_loop.jl

 - Input: tidal_range_2099_tide_highres_all.nc NetCDF file with tidal indicators (HAT, LAT, MHHW, MLLW and MSL) at point locations. Obtained from Sanne Muis and Jose Antonio Alvarez Antolinez.
 - Input: gebco_30sec_16.nc NetCDF file with global bathymetry dataset which is used as land-sea mask in the interpolation
 - Output: gtsm_interpolate_tide_loop.nc NetCDF file with tidal indicators (HAT, LAT, MHHW, MLLW and MSL) interpolated to a raster using DIVAnd
 - Settings for DIVAnd: see comments in the script itself
 
## tide.py

 - Input: gtsm_interpolate_tide_loop.nc file as produced by gtsm_interpolate_tide_loop.jl
 - Output: gtsm_tidal_indicators.tif GeoTiff file with the tidal indicators (HAT, LAT, MHHW, MLLW and MSL) added as bands
 
 Note: ran into some issues parsing the data to GeoTiffs in Julia, and hence modified existing Python script as used for other datasets as well.

## gtsm_interpolate_rp_loop.jl

 - Input: return_periods_new.csv CSV file with maximum water levels associated with 2, 5, 10, 25, 50, 75 and 100 year return periods. Obtained from Sanne Muis and Jose Antonio Alvarez Antolinez. Data manually converted from a Python pandas dataframe to a CSV, to be used by Julia script. Note: did not investigate option to directly load data fromm pandas pickle in Julia. 
 - Input: 03_ERA5_id_lon_lat_bedlev.xyzn coordinates for locations as used in return_periods_new.csv. Obtained from Sanne Muis and Jose Antonio Alvarez Antolinez., and used as is.
 - Input: gebco_30sec_16.nc NetCDF file with global bathymetry dataset which is used as land-sea mask in the interpolation
 - Output: gtsm_interpolate_rp_loop.nc NetCDF file with maximum water levels associated with 2, 5, 10, 25, 50, 75 and 100 year return periods, interpolated to a raster using DIVAnd
 - Settings for DIVAnd: see comments in the script itself
 
## returnperiod.py

 - Input: gtsm_interpolate_rp_loop.nc file as produced by gtsm_interpolate_rp_loop.jl
 - Output: gtsm_waterlevel_return_period.tif GeoTiff file with maximum water levels associated with 2, 5, 10, 25, 50, 75 and 100 year return periods added as bands
 
## prep_dirs.jl

 - Script to prepare output directories for gtsm_interpolate_tide_loop.jl and gtsm_interpolate_rp_loop.jl (used as is from DIVAnd example scripts)