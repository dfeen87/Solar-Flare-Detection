# test_energy_transfer.jl — Unit tests for tools/energy_transfer/EnergyTransfer.jl

using Test

include(joinpath(@__DIR__, "..", "tools", "energy_transfer", "EnergyTransfer.jl"))
using .EnergyTransfer

@testset "EnergyTransfer" begin

    @testset "rolling_variance — constant vector has zero variance" begin
        x = fill(5.0, 20)
        v = rolling_variance(x, 5)
        @test all(isnan, v[1:4])
        @test all(v[5:end] .≈ 0.0)
    end

    @testset "rolling_variance — first L-1 elements are NaN" begin
        x = collect(1.0:50.0)
        v = rolling_variance(x, 10)
        @test all(isnan, v[1:9])
        @test !isnan(v[10])
    end

    @testset "rolling_variance — known linear ramp" begin
        # Window [1,2,3,4,5]: mean=3, variance = mean((x-3)^2) = (4+1+0+1+4)/5 = 2
        x = collect(1.0:10.0)
        v = rolling_variance(x, 5)
        @test v[5] ≈ 2.0
    end

    @testset "rolling_variance — output length matches input" begin
        x = rand(100)
        @test length(rolling_variance(x, 15)) == 100
    end

    @testset "euv_derivative — linear function has constant derivative" begin
        # f(t) = 2t, so |df/dt| = 2 everywhere
        euv = collect(0.0:2.0:20.0)   # 11 points, step dt=1, values 0,2,4,...,20
        dt = 1.0
        d = euv_derivative(euv, dt)
        @test length(d) == length(euv)
        # Interior points via central difference: (f[i+1]-f[i-1])/(2*1) = (2*(i+1)*dt - 2*(i-1)*dt)/(2*1)
        # But euv values are 0,2,4,... so central difference = (4)/2 = 2.0
        for i in 2:length(euv)-1
            @test d[i] ≈ 2.0
        end
        # Endpoint one-sided differences also give 2.0
        @test d[1] ≈ 2.0
        @test d[end] ≈ 2.0
    end

    @testset "euv_derivative — returns non-negative values" begin
        euv = sin.(collect(0.0:0.1:10.0))
        d = euv_derivative(euv, 0.1)
        @test all(d .>= 0.0)
    end

    @testset "composite_indicator — equal weights sum to mean" begin
        a = [0.2, 0.4, 0.6]
        b = [0.3, 0.5, 0.7]
        c = [0.1, 0.3, 0.5]
        ind = composite_indicator(a, b, c)
        expected = (a .+ b .+ c) ./ 3
        @test ind ≈ expected
    end

    @testset "composite_indicator — custom weights" begin
        a = [1.0]
        b = [0.0]
        c = [0.0]
        ind = composite_indicator(a, b, c; w1=0.5, w2=0.3, w3=0.2)
        @test ind[1] ≈ 0.5
    end

end
