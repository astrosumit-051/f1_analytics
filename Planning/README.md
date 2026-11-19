# F1 Pit Wall Planning Documents

Use the data reference before changing code, then follow the coding procedure in order. The procedure is written for R and Shiny and contains 22 stages with numbered substeps, expected outputs, and completion criteria.

- [Data and code reference](F1_Data_and_Code_Reference.md) explains the source folders, file roles, metric definitions, data relationships, open quality questions, and planned code ownership.
- [Coding procedure](F1_Step_by_Step_Coding_Procedure.md) lays out the implementation from source validation through modeling, simulation, Shiny, testing, and presentation.
- The matching `.docx` files are formatted copies for reading and sharing. Update the Markdown text first, then regenerate the Word copies when the plan changes.
- [File inventory](F1_File_Inventory.csv) covers all 1,565 original files with intended use, exact paths, sizes, CSV dimensions, and source hashes.
- [Field dictionary](F1_Field_Dictionary.csv) documents 519 field entries across the 16 CSV table families, including decision-time availability and metric cautions.
- [Session index](F1_Session_Index.csv) covers all 193 race folders and their row counts and provenance.

The source exports and original proposal were preserved. Planned R modules are not implemented by this documentation task. The `_audit` directory retains inspection scripts, profiling evidence, and document verification intermediates; it is not part of the future application runtime.


## Coding ownership

See [the two-person coding work plan](F1_Two_Person_Work_Plan.md) for the six major ownership areas, assigned GitHub issues, and handoffs. Aiden owns data preparation, models, and analytical validation. Sumit owns the simulator, Shiny, and integrated builds.

The `_audit` evidence and render intermediates remain in the local workspace; the published planning files include the source inventory, field dictionary, and session index.
