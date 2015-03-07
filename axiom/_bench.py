"""
Utilities for benchmarking.
"""
import time
import sys
from itertools import islice



def mean(values):
    """
    Calculate the mean of a sequence.
    """
    values = list(values)
    return sum(values) / len(values)



def bench(op, wrap=lambda f: f(), prepare=lambda: None, loops=0, extraFactor=1,
          stepTime=1.0, samples=20, outliers=2, threshold=0.01):
    """
    Benchmark an operation.

    @type  op: C{callable}
    @param op: The operation to benchmark, called with no arguments.

    @type  stepTime: L{float}
    @param stepTime: Target time in seconds for each benchmark sample; the
        operation will be run (approximately) as many times as necessary to
        reach this target, in an attempt to minimize the effect of overhead
        from the benchmarking harness on very fast/cheap operations.

    @type  samples: L{int}
    @param samples: The number of benchmark samples to consider.

    @type  outliers: L{int}
    @param outliers: The number of outlier samples to discard.

    @type  threshold: L{float}
    @param threshold: Maximum variation coefficient to allow. The benchmark
        will be run until the coefficient of variation of the considered
        samples is below this value.
    """
    totalStart = time.time()

    if loops == 0:
        sys.stdout.write('Calibrating...')
        sys.stdout.flush()
        def _calibrate():
            loops = 0
            start = time.time()
            while time.time() - start < stepTime * 5:
                op()
                loops += 1
            return int(loops / 5)
        sys.stdout.write('{} loops\n'.format(wrap(_calibrate)))
        return

    def _runIteration():
        for n in xrange(loops):
            op()

    times = []
    while True:
        prepare()
        start = time.time()
        wrap(_runIteration)
        end = time.time()
        lastTime = (end - start) / (loops * extraFactor)
        times.insert(0, lastTime)
        if len(times) <= outliers:
            continue

        lastSlice = list(islice(times, samples + outliers))
        meanTime = mean(lastSlice)
        lastSlice = sorted(
            lastSlice, key=lambda x: abs(x - meanTime))[:-outliers]
        meanTime = mean(lastSlice)
        variationCoefficient = mean((x - meanTime) ** 2 for x in lastSlice) ** 0.5 / meanTime
        cumulativeTime = time.time() - totalStart
        sys.stdout.write('\r[{:0.2f}] {:0.16f} ({:0.16f})'.format(
            cumulativeTime, meanTime, variationCoefficient))
        sys.stdout.flush()
        if len(times) > samples and variationCoefficient < threshold:
            break
    print
