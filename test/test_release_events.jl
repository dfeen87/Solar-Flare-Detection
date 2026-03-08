# test_release_events.jl — Unit tests for tools/release_events/ReleaseEvents.jl

using Test
using Dates

include(joinpath(@__DIR__, "..", "tools", "release_events", "ReleaseEvents.jl"))
using .ReleaseEvents

@testset "ReleaseEvents" begin

    @testset "overlay_events — returns correct NamedTuple structure" begin
        ts = (times=[DateTime(2025,1,1), DateTime(2025,1,2)],
              values=[0.5, 0.8])
        events = [
            FlareEvent(DateTime(2025,1,1,12), "M", 1e-5),
            FlareEvent(DateTime(2025,1,2,6),  "X", 5e-5),
        ]
        result = overlay_events(ts, events)
        @test haskey(result, :series)
        @test haskey(result, :events)
        @test haskey(result, :classes)
        @test result.series  === ts
        @test result.events  === events
        @test result.classes == ["M", "X"]
    end

    @testset "overlay_events — empty events list" begin
        ts = (times=DateTime[], values=Float64[])
        result = overlay_events(ts, FlareEvent[])
        @test isempty(result.events)
        @test isempty(result.classes)
    end

    @testset "compute_lead_times — single flare with one preceding peak" begin
        # Flare at t=100s, peak at t=40s → lead = 60s
        t0 = DateTime(2025, 1, 1)
        flare_times = [t0 + Second(100)]
        peaks = (
            times  = [t0 + Second(40)],
            values = [1.0],
        )
        lt = compute_lead_times(flare_times, peaks)
        @test length(lt) == 1
        @test lt[1] ≈ 60.0
    end

    @testset "compute_lead_times — no preceding peak returns NaN" begin
        t0 = DateTime(2025, 1, 1)
        flare_times = [t0 + Second(10)]
        peaks = (
            times  = [t0 + Second(50)],   # peak is AFTER flare
            values = [1.0],
        )
        lt = compute_lead_times(flare_times, peaks)
        @test isnan(lt[1])
    end

    @testset "compute_lead_times — picks closest preceding peak" begin
        t0 = DateTime(2025, 1, 1)
        flare_times = [t0 + Second(200)]
        peaks = (
            times  = [t0 + Second(50), t0 + Second(180)],
            values = [0.5, 0.9],
        )
        lt = compute_lead_times(flare_times, peaks)
        # Both 50 and 180 precede the flare; smallest lead time = 200-180 = 20s
        @test lt[1] ≈ 20.0
    end

    @testset "compute_lead_times — multiple flares" begin
        t0 = DateTime(2025, 1, 1)
        flare_times = [t0 + Second(100), t0 + Second(300)]
        peaks = (
            times  = [t0 + Second(80), t0 + Second(250)],
            values = [1.0, 1.0],
        )
        lt = compute_lead_times(flare_times, peaks)
        @test lt[1] ≈ 20.0
        @test lt[2] ≈ 50.0
    end

end
