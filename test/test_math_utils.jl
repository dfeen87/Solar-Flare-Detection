# test_math_utils.jl — Unit tests for shared/MathUtils.jl

using Test

include(joinpath(@__DIR__, "..", "shared", "MathUtils.jl"))
using .MathUtils

@testset "MathUtils" begin

    # -----------------------------------------------------------------------
    # normalize_01
    # -----------------------------------------------------------------------

    @testset "normalize_01 — basic normalization" begin
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        n = normalize_01(x)
        @test n[1] ≈ 0.0
        @test n[end] ≈ 1.0
        @test n[3] ≈ 0.5
    end

    @testset "normalize_01 — constant input returns zeros" begin
        x = fill(7.0, 10)
        n = normalize_01(x)
        @test all(n .≈ 0.0)
    end

    @testset "normalize_01 — all-NaN input returns copy" begin
        x = fill(NaN, 5)
        n = normalize_01(x)
        @test all(isnan, n)
    end

    @testset "normalize_01 — mixed NaN input preserves NaN positions" begin
        x = [NaN, 0.0, 2.0, 4.0, NaN]
        n = normalize_01(x)
        @test isnan(n[1])
        @test isnan(n[5])
        @test n[2] ≈ 0.0
        @test n[3] ≈ 0.5
        @test n[4] ≈ 1.0
    end

    @testset "normalize_01 — output length matches input" begin
        x = rand(30)
        @test length(normalize_01(x)) == 30
    end

    # -----------------------------------------------------------------------
    # rolling_correlation
    # -----------------------------------------------------------------------

    @testset "rolling_correlation — perfect positive correlation" begin
        x = collect(1.0:20.0)
        y = collect(1.0:20.0)
        c = rolling_correlation(x, y, 5)
        @test all(isnan, c[1:4])
        @test all(c[5:end] .≈ 1.0)
    end

    @testset "rolling_correlation — perfect negative correlation" begin
        x = collect(1.0:20.0)
        y = collect(20.0:-1.0:1.0)
        c = rolling_correlation(x, y, 5)
        @test all(isnan, c[1:4])
        @test all(c[5:end] .≈ -1.0)
    end

    @testset "rolling_correlation — constant signals give zero correlation" begin
        x = fill(3.0, 20)
        y = fill(5.0, 20)
        c = rolling_correlation(x, y, 5)
        @test all(isnan, c[1:4])
        @test all(c[5:end] .≈ 0.0)
    end

    @testset "rolling_correlation — window larger than data gives all NaN" begin
        x = [1.0, 2.0, 3.0]
        y = [3.0, 2.0, 1.0]
        c = rolling_correlation(x, y, 10)
        @test all(isnan, c)
    end

    @testset "rolling_correlation — output length matches input" begin
        x = rand(50)
        y = rand(50)
        @test length(rolling_correlation(x, y, 10)) == 50
    end

    @testset "rolling_correlation — first L-1 elements are NaN" begin
        x = collect(1.0:30.0)
        y = collect(30.0:-1.0:1.0)
        c = rolling_correlation(x, y, 10)
        @test all(isnan, c[1:9])
        @test !isnan(c[10])
    end

end
