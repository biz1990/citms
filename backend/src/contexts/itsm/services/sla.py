import pandas as pd
from business_duration import businessDuration
import holidays as pyholidays
from datetime import datetime, time, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.itsm.models import SystemHoliday, TicketPriority

class SlaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Business hours: 08:00 - 17:00
        self.work_start = time(8, 0)
        self.work_end = time(17, 0)

    async def calculate_deadline(self, start_time: datetime, priority: TicketPriority) -> datetime:
        """Calculate SLA deadline using business_duration library."""
        # SLA hours by priority
        sla_hours = {
            TicketPriority.LOW: 48,
            TicketPriority.MEDIUM: 24,
            TicketPriority.HIGH: 8,
            TicketPriority.CRITICAL: 4
        }.get(priority, 24)

        # Get holidays from DB
        res = await self.db.execute(select(SystemHoliday.holiday_date))
        db_holidays = {h for h in res.scalars().all()}
        
        # Merge with standard VN holidays (or user-defined)
        vn_holidays = pyholidays.VN()
        holiday_list = list(set(list(db_holidays) + list(vn_holidays.keys())))

        # Note: business_duration.businessDuration calculates duration between TWO dates.
        # To find a DEADLINE, we need to find a date such that duration(start, deadline) == sla_hours.
        # This library is mainly for DURATION. For DEADLINE, we might still need a loop, 
        # but we use the library's logic for business days/hours.
        
        current_deadline = start_time
        remaining_hours = float(sla_hours)
        
        # Optimization: jump by days first if remaining_hours > work_day_duration
        work_day_hours = 8.0 # 8:00 to 17:00 minus lunch is usually 8, but here 9 hours total.
        
        # Helper to check if a date is business day
        def is_biz_day(d):
            return d.weekday() < 5 and d.date() not in holiday_list

        while remaining_hours > 0:
            if not is_biz_day(current_deadline) or current_deadline.time() >= self.work_end:
                current_deadline = (current_deadline + timedelta(days=1)).replace(hour=8, minute=0, second=0)
                continue
            
            if current_deadline.time() < self.work_start:
                current_deadline = current_deadline.replace(hour=8, minute=0, second=0)

            day_end = current_deadline.replace(hour=17, minute=0, second=0)
            
            # Use businessDuration to accurately check current day's capacity
            # businessDuration returns 0 if same time, so we check capacity until day_end
            capacity_seconds = businessDuration(
                startdate=pd.to_datetime(current_deadline),
                enddate=pd.to_datetime(day_end),
                starttime=self.work_start,
                endtime=self.work_end,
                holidaylist=holiday_list,
                unit='sec'
            )
            capacity_hours = capacity_seconds / 3600.0

            if remaining_hours <= capacity_hours:
                # Find exact time within this day
                current_deadline += timedelta(hours=remaining_hours)
                remaining_hours = 0
            else:
                remaining_hours -= capacity_hours
                current_deadline = (current_deadline + timedelta(days=1)).replace(hour=8, minute=0, second=0)

        return current_deadline
