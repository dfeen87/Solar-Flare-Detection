# test_topology.jl — Unit tests for tools/topology/Topology.jl

using Test

include(joinpath(@__DIR__, "..", "tools", "topology", "Topology.jl"))
using .Topology

@testset "Topology" begin

    @testset "rolling_variance_B — matches rolling_variance algorithm" begin
        B = collect(1.0:20.0)
        L = 5
        v = rolling_variance_B(B, L)
        # First L-1 are NaN
        @test all(isnan, v[1:L-1])
        # Window [1,2,3,4,5]: mean=3, variance = 2
        @test v[L] ≈ 2.0
    end

    @testset "rolling_variance_B — constant signal has zero variance" begin
        B = fill(42.0, 30)
        v = rolling_variance_B(B, 10)
        @test all(isnan, v[1:9])
        @test all(v[10:end] .≈ 0.0)
    end

    @testset "rolling_variance_B — output length matches input" begin
        B = rand(80)
        @test length(rolling_variance_B(B, 12)) == 80
    end

    @testset "compute_chi — constant variance gives linear ramp" begin
        # var_B = [NaN, NaN, 1, 1, 1, 1] (window L=3)
        var_B = [NaN, NaN, 1.0, 1.0, 1.0, 1.0]
        dt = 1.0
        chi = compute_chi(var_B, dt)
        # First two entries remain NaN
        @test all(isnan, chi[1:2])
        # chi[3] = 0 (starting value)
        @test chi[3] ≈ 0.0
        # Each subsequent step adds trapezoid area: 0.5*(1+1)*1 = 1
        @test chi[4] ≈ 1.0
        @test chi[5] ≈ 2.0
        @test chi[6] ≈ 3.0
    end

    @testset "compute_chi — preserves NaN region" begin
        # Window L=5; first 4 are NaN
        B = rand(20)
        var_B = rolling_variance_B(B, 5)
        chi = compute_chi(var_B, 1.0)
        @test all(isnan, chi[1:4])
        @test !isnan(chi[5])
    end

    @testset "compute_chi — monotonically non-decreasing for non-negative variance" begin
        B = abs.(randn(50))
        var_B = rolling_variance_B(B, 5)
        dt = 1.0
        chi = compute_chi(var_B, dt)
        valid = chi[.!isnan.(chi)]
        @test all(diff(valid) .>= 0.0)
    end

end
