from sindri.benchmark.runner import run_benchmark, format_scorecard


def main() -> None:
    print(format_scorecard(run_benchmark()))


if __name__ == "__main__":
    main()
