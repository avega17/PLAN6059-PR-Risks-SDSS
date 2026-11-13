# Third-party notices

## autobox: ArcGIS toolbox serialization pattern

`tools/build_toolbox.py` adapts the small ArcGIS `.atbx` Zip/JSON serialization pattern from [autobox](https://github.com/realiii/autobox), inspected commit [`298c57385cdede8b3417cc7b736a066febd874a9`](https://github.com/realiii/autobox/tree/298c57385cdede8b3417cc7b736a066febd874a9). In particular, the toolbox/tool content-resource structure, parameter JSON structure and relative execution-link convention follow its `toolbox.py`, `script.py`, `parameter.py`, `constant.py` and `filter.py` examples. This repository contains a small purpose-built builder, not an installation or vendored copy of the complete autobox package.

The upstream license is reproduced below. Retain this notice with distributions containing the builder or generated toolbox.

> MIT License
>
> Copyright (c) 2024-2025 Integrated Informatics (USA) Inc.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

## Research references

The deferred estimation note links HURRECON, CLIMADA, Tropycal and tcwind for comparison. No source from those packages is incorporated in this prototype. Their licenses must be assessed and notices retained if code is incorporated in a future implementation; citations alone are not a substitute for license terms.
