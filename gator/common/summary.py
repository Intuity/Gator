# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Dict, List, Optional, TypedDict


class Summary(TypedDict):
    metrics: Dict[str, int]
    failed_ids: List[List[str]]


def make_summary(
    metrics: Optional[Dict[str, int]] = None,
    failed_ids: Optional[List[List[str]]] = None,
):
    return Summary(
        failed_ids=failed_ids or [],
        metrics=metrics or {},
    )


def contextualise_summary(context: str, summary: Summary):
    new_summary = make_summary(**summary)
    new_summary["failed_ids"] = [[context, *x] for x in summary["failed_ids"]]
    return new_summary


def merge_summaries(*summaries: Summary, base: Optional[Summary] = None):
    if base is None:
        base = make_summary()
    for summary in summaries:
        for m_key, m_val in summary["metrics"].items():
            base["metrics"][m_key] = base["metrics"].get(m_key, 0) + m_val
        base["failed_ids"] += summary["failed_ids"]
    return base
