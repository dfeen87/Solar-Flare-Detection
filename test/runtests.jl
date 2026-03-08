# runtests.jl — Master test runner for Solar Flare Detection Julia modules

using Test

@testset "Solar Flare Detection — Julia Unit Tests" begin
    include("test_energy_transfer.jl")
    include("test_topology.jl")
    include("test_spiral_time.jl")
    include("test_release_events.jl")
end
