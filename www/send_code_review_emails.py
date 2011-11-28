import optparse

def parse_args():
    parser = optparse.OptionParser(
        description="Nightly job to email people who haven't completed their"
                    " code reviews",
    )
    parser.add_option('--dry-run', default=False, action='store_true',
        dest='dryrun', help="Don't actually email anyone"
    )
    parser.add_option('--force', default=False, action='store_true',
        dest='force', help="Run, even if this script has run before"
    )
    return parser.parse_args()[0]

def main(args):
    from lib.codeReview import nightly_email
    nightly_email(dryrun=args.dryrun, force=args.force)

if __name__ == '__main__':
    main(parse_args())
