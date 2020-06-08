using DIVAnd
using PyPlot
using NCDatasets
using Dates
using Statistics
using Printf
using CSV
using GeoArrays
using NetCDF

include("./prep_dirs.jl")

fname_periods = joinpath(dirname(@__FILE__),"..","GTSM","return_periods_new.csv")
fname_coordinates = joinpath(dirname(@__FILE__),"..","GTSM","03_ERA5_id_lon_lat_bedlev.xyzn")
bathname = joinpath(dirname(@__FILE__),"gebco_30sec_16.nc")

isglobal = true

# Define input observations ##

coord = CSV.read(fname_coordinates)
lon = coord[:,2]
lat = coord[:,3]

rp = CSV.read(fname_periods)

# Read one of the return periods as an example
rp = rp[:,5]

# Define output grid
# Higher resulotion results in out-of-memory issues

dx = dy = 0.1

lonr = -180:dx:180
latr = -85:dy:85

# Specify minimum value for the input, to remove faulty values
limit = 0.0001

# error variance of the observations (copied this from an example, need to investigate what a proper value would be)
epsilon2 = 0.1


# Plot the input
figure(1)

vmin = minimum(rp[rp .> limit])
vmax = maximum(rp[rp .> limit])

scatter(lon[rp .> limit],lat[rp .> limit],10,rp[rp .> limit],cmap = "jet")

xlim(minimum(lonr),maximum(lonr))
ylim(minimum(latr),maximum(latr))

colorbar()

# Define mask
mask,(pm,pn),(xi,yi) = domain(bathname,isglobal,lonr,latr)

# pm array as defined by mask function contains faulty values which cause problems. Set pm to pn to resolve
pm = pn

# correlation length of 300km, based on some trial and error (lower values results in patchiness on open ocean)
len = 300_000

#Go!
# moddim=[1,0] --> cyclical in the lon dimension, to get matching results at lat = +/- 180
@time fi,s = DIVAndrun(mask,(pm,pn),(xi,yi),(lon[rp .> limit],lat[rp .> limit]),rp[rp .> limit],len,epsilon2; moddim=[1,0]);

# Plot the output
figure(2)
pcolor(xi,yi,fi,cmap = "jet", vmin = vmin, vmax = vmax);
colorbar()
title("Interpolated field");
