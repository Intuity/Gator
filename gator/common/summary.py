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

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, TypedDict, cast


class SummaryDict(TypedDict):
    metrics: Dict[str, int]
    failed_ids: List[List[str]]


@dataclass
class Summary:
    metrics: Dict[str, int] = field(default_factory=dict)
    failed_ids: List[List[str]] = field(default_factory=list)

    def from_dict(self, data: SummaryDict) -> "Summary":
        return type(self)(**data)

    def as_dict(self) -> SummaryDict:
        return cast(SummaryDict, asdict(self))

    def contextualised(self, context: str) -> "Summary":
        new_summary = type(self)(**asdict(self))
        new_summary.failed_ids = [[context, *x] for x in self.failed_ids]
        return new_summary

    def merged(
        self: "Summary", *summaries: "Summary", base: Optional["Summary"] = None
    ) -> "Summary":
        if base is None:
            base = Summary()
        for summary in (self, *summaries):
            for m_key, m_val in summary.metrics.items():
                base.metrics[m_key] = base.metrics.get(m_key, 0) + m_val
            base.failed_ids += summary.failed_ids
        return base

    @property
    def passed(self):
        metrics = self.metrics
        if (
            (len(self.failed_ids) == 0)
            and (metrics["sub_passed"] == metrics["sub_total"])
            and (metrics["msg_error"] == 0)
            and (metrics["msg_critical"] == 0)
        ):
            return True
        return False

    @property
    def failed(self):
        return not self.passed
