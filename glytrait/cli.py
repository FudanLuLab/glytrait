from pathlib import Path

import click
import emoji

from glytrait.config import Config
from glytrait.core import run_workflow
from glytrait.exception import GlyTraitError
from glytrait.trait import save_trait_formula_template

UNDIFINED = "__UNDEFINED__"


def save_template_callback(ctx, param, value):
    """Save a template for the user to fill in."""
    if value == UNDIFINED:
        return
    if Path(value).exists() and not Path(value).is_dir():
        raise click.BadParameter("The path to save the template must be a directory.")
    else:
        save_trait_formula_template(value)
        msg = (
            f"Template saved to {value}. :victory_hand:\n"
            f"You can edit the template and use `glytrait INPUT_FILE OUTPUT_FILE -f "
            f"TEMPLATE_FILE` to provide additional traits to glyTrait."
        )
        click.echo(emoji.emojize(msg))
        ctx.exit()


@click.command()
@click.argument(
    "input-file",
    type=click.Path(exists=True),
    required=False,
)
@click.option(
    "-o",
    "--output-file",
    type=click.Path(),
    help="Output file path. Default is the input file name with '_glytrait.xlsx' "
    "suffix.",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["structure", "composition", "S", "C"]),
    default="structure",
    help="Mode to run glyTrait, either 'structure' or 'composition'. "
    "You can also use 'S' or 'C' for short. "
    "Default is 'structure'.",
)
@click.option(
    "-r",
    "--filter-glycan-ratio",
    type=click.FLOAT,
    default=0.5,
    help="Glycans with missing value ratio greater than this value will be filtered out.",
)
@click.option(
    "-i",
    "--impute-method",
    type=click.Choice(["zero", "min", "lod", "mean", "median"]),
    default="min",
    help="Method to impute missing values.",
)
@click.option(
    "-l", "--sia-linkage", is_flag=True, help="Include sialic acid linkage traits."
)
@click.option(
    "-f",
    "--formula-file",
    type=click.Path(exists=True),
    help="User formula file.",
)
@click.option(
    "-t",
    "--save-template",
    type=click.Path(),
    callback=save_template_callback,
    is_eager=True,
    expose_value=False,
    default=UNDIFINED,
    help="The directory path to save the formular template file.",
)
@click.option(
    "--filter/--no-filter",
    default=True,
    help="Filter out invalid derived traits. Default is filtering."
    "Use --no-filter to disable filtering.",
)
@click.option(
    "-g",
    "--group-file",
    type=click.Path(exists=True),
    help="Group file for hypothesis test.",
)
@click.option(
    "-s",
    "--structure-file",
    type=click.Path(exists=True),
    help="Structure file for hypothesis test.",
)
@click.option(
    "-d",
    "--database",
    type=click.STRING,
    help="Built-in database to use, either 'serum' or 'IgG'.",
)
@click.version_option()
def cli(
    input_file,
    output_file,
    mode,
    filter_glycan_ratio,
    impute_method,
    sia_linkage,
    formula_file,
    filter,
    group_file,
    structure_file,
    database,
):
    """Run the glytrait workflow."""
    if output_file is None:
        output_file = str(
            Path(input_file).with_name(Path(input_file).stem + "_glytrait.xlsx")
        )
    else:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    mode = "composition" if mode.lower() in ["c", "composition"] else "structure"
    try:
        config = Config(
            dict(
                input_file=input_file,
                output_file=output_file,
                mode=mode,
                filter_glycan_max_na=filter_glycan_ratio,
                impute_method=impute_method,
                sia_linkage=sia_linkage,
                formula_file=formula_file,
                filter_invalid_traits=filter,
                group_file=group_file,
                structure_file=structure_file,
                database=database,
            )
        )
        run_workflow(config)
    except GlyTraitError as e:
        raise click.UsageError(str(e) + emoji.emojize(" :thumbs_down:"))
    msg = f"Done :thumbs_up:! Output written to {output_file}."
    click.echo(emoji.emojize(msg))


if __name__ == "__main__":
    cli()
