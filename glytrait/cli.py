import click
import emoji

from glytrait.workflow import run_workflow


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
def cli(input_file, output_file):
    """Run the glytrait workflow."""
    run_workflow(input_file, output_file)
    msg = f"Done :thumbs_up:! Output written to {output_file}."
    print(emoji.emojize(msg))


if __name__ == "__main__":
    cli()
