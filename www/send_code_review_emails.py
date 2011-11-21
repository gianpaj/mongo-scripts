import optparse

def parse_args():
    parser = optparse.OptionParser(description='Nightly job to email people who haven\'t completed their code reviews')
    parser.add_option('--dry-run', default=False, action='store_true', dest='dryrun', help='Don\'t actually email anyone')
    return parser.parse_args()[0]

def main(args):
    from lib.codeReview import nightly_email
    nightly_email(args.dryrun)

if __name__ == '__main__':
    main(parse_args())
