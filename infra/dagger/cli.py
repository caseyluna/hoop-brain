# infra/dagger/cli.py

import argparse
import json
import sys
import time
import traceback

import anyio
import dagger
from orchestrator import DaggerOrchestrator
from utils import flatten_results, print_summary


def build_arg_parser(pipelines_config, services_config):
    parser = argparse.ArgumentParser(
        description="Dagger CLI for CI/CD pipelines",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--env",
        choices=["test", "prod"],
        default="test",
        help="Environment to use: 'test' or 'prod' (default: test)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output, only show summary",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    check_parser = subparsers.add_parser(
        "check", help="Run a specific check for a service"
    )
    check_parser.add_argument(
        "service",
        choices=list(services_config.keys()),
        help="Service to run the check on",
    )
    check_parser.add_argument("check", help="Name of the check to run")

    # job
    job_parser = subparsers.add_parser("job", help="Run a specific job for a service")
    job_parser.add_argument(
        "service",
        choices=list(services_config.keys()),
        help="Service to run the job on",
    )
    job_parser.add_argument("job", help="Name of the job to run")
    job_parser.add_argument(
        "job_args", nargs=argparse.REMAINDER, help="Arguments for the job"
    )

    # all-checks-for-service
    acfs_parser = subparsers.add_parser(
        "all-checks-for-service",
        help="Run all checks for a specific service",
    )
    acfs_parser.add_argument(
        "service",
        choices=list(services_config.keys()),
        help="Service to run all checks on",
    )

    # all-checks
    ac_parser = subparsers.add_parser(
        "all-checks", help="Run all checks for all or specified services"
    )
    ac_parser.add_argument(
        "services",
        choices=list(services_config.keys()),
        help="Services to run all checks on (default: all services)",
    )
    subparsers.add_parser("integration-test", help="Run full integration test")
    for pipeline_name in pipelines_config.keys():
        subparsers.add_parser(
            pipeline_name,
            help=f"Run the '{pipeline_name}' pipeline defined in pipelines.yaml",
        )
    return parser


async def main():
    try:
        # load configs to build parser
        async with dagger.Connection() as client:
            orch = DaggerOrchestrator(client)
            pipelines_config = orch.pipelines_config
            services_config = orch.services_config
            print("Args:", sys.argv)
            print(f"Loaded services: {list(services_config.keys())}")
            parser = build_arg_parser(pipelines_config, services_config)
            args = parser.parse_args()

            # set the DB URL based on the environment
            db_url = (
                "postgresql://postgres:postgres@db:5432/hoopbrain"
                if args.env == "prod"
                else "postgresql://postgres:postgres@db:5432/hoopbrain_test"
            )
            orch.db_url = db_url
            overall_start = time.perf_counter()
            if args.command == "check":
                results = [await orch.run_check(args.service, args.check)]
            elif args.command == "job":
                results = [await orch.run_job(args.service, args.job, args.job_args)]
            elif args.command == "integration-test":
                await orch.run_integration_test()
            elif args.command == "all-checks-for-service":
                results = await orch.run_all_checks_for_service(args.service)
            elif args.command == "all-checks":
                services = (
                    args.services if args.services else list(services_config.keys())
                )
                results = await orch.run_all_checks_for_services_parallel(services)
            elif args.command in pipelines_config:
                results = await orch.run_pipeline(args.command)
            else:
                parser.print_help()
                sys.exit(1)
            overall_duration = time.perf_counter() - overall_start
            results = flatten_results(results)
            if args.json:
                print(
                    json.dumps(
                        {"results": results, "total_time": overall_duration}, indent=2
                    )
                )
            elif not args.quiet:
                print_summary(results, overall_duration)
    except Exception as e:
        if "--debut" in sys.argv:
            traceback.print_exc()
        else:
            print(f"\n[ERROR]: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
