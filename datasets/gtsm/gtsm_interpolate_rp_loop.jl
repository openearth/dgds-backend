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

# Loop over all return periods
period = [2,5,10,25,50,75,100]
column = [3,4,5,6,7,8,9]

# Define input observations ##

coord = CSV.read(fname_coordinates)
lon = coord[:,2]
lat = coord[:,3]

for n in 1:7

	rp = CSV.read(fname_periods)

    # Read one of the return periods
	rp = rp[:,column[n]]

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
	filename = joinpath(outputdir, basename(replace(@__FILE__,r".jl$" => ".nc")))
	@info "Output file: " * filename

	varname = string("waterlevel_", string(period[n]))
	varname_atts = string("Water level return period ", string(period[n]))

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
