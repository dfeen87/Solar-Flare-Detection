# test_spiral_time.jl — Unit tests for tools/spiral_time/SpiralTime.jl

using Test

include(joinpath(@__DIR__, "..", "tools", "spiral_time", "SpiralTime.jl"))
using .SpiralTime

@testset "SpiralTime" begin

    @testset "classify_regime — isostasis below 0.15" begin
        @test classify_regime(0.0).regime  == :isostasis
        @test classify_regime(0.10).regime == :isostasis
        @test classify_regime(0.14).regime == :isostasis
    end

    @testset "classify_regime — allostasis in [0.15, 0.35)" begin
        @test classify_regime(0.15).regime == :allostasis
        @test classify_regime(0.25).regime == :allostasis
        @test classify_regime(0.34).regime == :allostasis
    end

    @testset "classify_regime — high_allostasis in [0.35, 0.40)" begin
        @test classify_regime(0.35).regime == :high_allostasis
        @test classify_regime(0.37).regime == :high_allostasis
        @test classify_regime(0.399).regime == :high_allostasis
    end

    @testset "classify_regime — collapse at and above 0.40" begin
        @test classify_regime(0.40).regime == :collapse
        @test classify_regime(0.75).regime == :collapse
        @test classify_regime(1.0).regime  == :collapse
    end

    @testset "classify_regime — returns RegimeClassification" begin
        result = classify_regime(0.05)
        @test result isa RegimeClassification
    end

    @testset "compute_psi — returns PhaseMemoryState with correct fields" begin
        psi = compute_psi(1.0, 0.5, 0.3)
        @test psi isa PhaseMemoryState
        @test psi.t   ≈ 1.0
        @test psi.phi ≈ 0.5
        @test psi.chi ≈ 0.3
    end

    @testset "compute_delta_phi — constant signals give ΔΦ = 0" begin
        S = fill(1.0, 10)
        I = fill(2.0, 10)
        C = fill(0.5, 10)
        dp = compute_delta_phi(S, I, C)
        @test isnan(dp[1])
        @test all(dp[2:end] .≈ 0.0)
    end

    @testset "compute_delta_phi — output length matches inputs" begin
        n = 50
        S = rand(n); I = rand(n); C = rand(n)
        @test length(compute_delta_phi(S, I, C)) == n
    end

    @testset "compute_delta_phi — first element is NaN" begin
        S = rand(5); I = rand(5); C = rand(5)
        dp = compute_delta_phi(S, I, C)
        @test isnan(dp[1])
    end

    @testset "compute_delta_phi — step function inputs" begin
        # S jumps by 1 at t=2, I and C constant → ΔΦ[2] = α*1 = 1/3
        S = [0.0, 1.0, 1.0, 1.0]
        I = [0.0, 0.0, 0.0, 0.0]
        C = [0.0, 0.0, 0.0, 0.0]
        dp = compute_delta_phi(S, I, C)
        @test isnan(dp[1])
        @test dp[2] ≈ 1/3
        @test dp[3] ≈ 0.0
        @test dp[4] ≈ 0.0
    end

    @testset "compute_delta_phi — custom weights" begin
        S = [0.0, 1.0]
        I = [0.0, 1.0]
        C = [0.0, 1.0]
        dp = compute_delta_phi(S, I, C; α=0.5, β=0.3, γ=0.2)
        @test isnan(dp[1])
        @test dp[2] ≈ 1.0   # 0.5*1 + 0.3*1 + 0.2*1 = 1.0
    end

end
