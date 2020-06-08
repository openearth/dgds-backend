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

fname = joinpath(dirname(@__FILE__),"..","GTSM","tidal_range_2099_tide_highres_all.nc")
bathname = joinpath(dirname(@__FILE__),"gebco_30sec_16.nc")

isglobal = true

# Define input observations ##

lon = ncread(fname, "station_x_coordinate")
lat = ncread(fname, "station_y_coordinate")

for n in 1:5

	if n == 1
	    varname = "HAT"
	   	varname_atts = string("Highest Astronomical Tide")
		limit = 999
	elseif n == 2
	    varname = "LAT"
	   	varname_atts = string("Lowest Astronomical Tide")
		limit = 999
	elseif n == 3
	    varname = "MHHW"
	   	varname_atts = string("Mean Higher High Water")
		limit = 999
	elseif n == 4
	    varname = "MLLW"
	   	varname_atts = string("Mean Lower Low Water")
		limit = 999
	elseif n == 5
	    varname = "MSL"
	   	varname_atts = string("Mean Sea Level")
		limit = 0.5
	end

	rp = CSV.read(fname_periods)

    # Read one of the tidal indicators
	rp_temp = ncread(fname, varname)'
    rp = rp_temp[:,1]

    # Define output grid
    # Higher resulotion results in out-of-memory issues
	dx = dy = 0.1

	lonr = -180:dx:180
	latr = -85:dy:85

    # Specify minimum value for the input, to remove faulty values
    limit = 0.0001

    # error variance of the observations (copied this from an example, need to investigate what a proper value would be)
	epsilon2 = 0.1

	mask,(pm,pn),(xi,yi) = domain(bathname,isglobal,lonr,latr)

    # pm array as defined by mask function contains faulty values which cause problems. Set pm to pn to resolve
	pm = pn

    # correlation length of 300km, based on some trial and error (lower values results in patchiness on open ocean)
	len = 300_000

    #Go!
    # moddim=[1,0] --> cyclical in the lon dimension, to get matching results at lat = +/- 180
	@time fi,s = DIVAndrun(mask,(pm,pn),(xi,yi),(lon[rp .> limit],lat[rp .> limit]),rp[rp .> limit],len,epsilon2; moddim=[1,0]);

    # Write NetCDF (see https://juliageo.org/NetCDF.jl/v0.5/quickstart.html)
	varatts = Dict("longname" => varname_atts,
			  "units"    => "m")
			  
		lonatts = Dict("longname" => "Longitude",
				  "units"    => "degrees east")
		latatts = Dict("longname" => "Latitude",
				  "units"    => "degrees north")

	filename = joinpath(outputdir, basename(replace(@__FILE__,r".jl$" => ".nc")))
	
	nccreate(filename,varname,"lon",xi[:,1],lonatts,"lat",yi[1,:],latatts,atts=varatts);

	ncwrite(fi,filename,varname);

end
