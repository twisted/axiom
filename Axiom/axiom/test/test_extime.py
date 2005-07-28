
import datetime
import time
import operator

from twisted.trial import unittest

from axiom import extime

class TestTime(unittest.TestCase):
    class MST(datetime.tzinfo):
        def tzname(self, dt):
            return 'MST'
        def utcoffset(self, dt):
            return datetime.timedelta(hours = -7)
        def dst(self, dt):
            return datetime.timedelta(0)

    class CET(datetime.tzinfo):
        def tzname(self, dt):
            return 'MST'
        def utcoffset(self, dt):
            return datetime.timedelta(hours = 1)
        def dst(self, dt):
            return datetime.timedelta(0)

    reference = datetime.datetime(2004, 12, 6, 14, 15, 16)
    awareReference = datetime.datetime(2004, 12, 6, 14, 15, 16, tzinfo=extime.FixedOffset(0, 0))

    def _checkReference(self, timeInstance, reference=None):
        """Check timeInstance against self.reference."""
        self.assertEquals(timeInstance._time, reference or self.reference)

    def _createReference(self, reference=None):
        """Return a refernce instance."""
        return extime.Time.fromDatetime(reference or self.reference)

    def testPytzWeirdness(self):
        """pytz weirdness; RT ticket #2755"""
        try:
            import pytz
        except ImportError:
            raise unittest.SkipTest, 'pytz could not be imported'
        tz = pytz.timezone('America/Detroit')
        time = extime.Time.fromRFC2822('Wed, 06 Apr 2005 23:12:27 -0400')
        dtime = time.asDatetime(tz)
        self.assertEquals(dtime.hour, 23)
        self.assertEquals(dtime.minute, 12)

    def testCmp(self):
        now = time.gmtime()
        self.assertEquals(extime.Time.fromStructTime(now), extime.Time.fromStructTime(now))
        self.assertNotEquals(extime.Time.fromStructTime(now), extime.Time.fromStructTime(time.localtime()))
        self.assertNotEquals(extime.Time.fromStructTime(now), 13)

        aTime = extime.Time.fromStructTime(now)
        for op in 'lt', 'le', 'gt', 'ge':
            self.assertRaises(TypeError, getattr(operator, op), aTime, now)

    def testFromNow(self):
        diff = datetime.datetime.utcnow() - extime.Time()._time
        if diff < datetime.timedelta():
            diff = -diff
        self.failUnless(diff.days == 0 and diff.seconds <= 5, 'Time created now is %r away from now' % (diff,))

    def testInsignificantTimezones(self):
        """Timezones should be insignificant when the resolution is >= 1 day"""
        def testEqual(creator, input):
            self.assertEquals(creator(input), creator(input, tzinfo=self.MST()))

        def testNotEqual(creator, input):
            self.assertNotEquals(creator(input), creator(input, tzinfo=self.MST()))

        testEqual(extime.Time.fromHumanly, 'sunday')
        testEqual(extime.Time.fromISO8601TimeAndDate, '2005')
        testEqual(extime.Time.fromISO8601TimeAndDate, '2005-02')
        testEqual(extime.Time.fromISO8601TimeAndDate, '2005-02-10')

        testNotEqual(extime.Time.fromISO8601TimeAndDate, '2005-02-10T12')
        testNotEqual(extime.Time.fromISO8601TimeAndDate, '2005-02-10T12:10')
        testNotEqual(extime.Time.fromISO8601TimeAndDate, '2005-02-10T12:10:03')

    def testFromHumanly(self):
        def test(input, expected, tzinfo=None):
            time = extime.Time.fromHumanly(
                input,
                tzinfo,
                self._createReference())

            self.assertEquals(
                time.asISO8601TimeAndDate(),
                expected)

            return time

        def testMalformed(input):
            self.assertRaises(ValueError, extime.Time.fromHumanly, input)

        def testDay(input, expected, tzinfo=None):
            time = test(input, expected, tzinfo)
            self.assert_(time.isAllDay())

        def testMinute(input, expected, tzinfo=None):
            time = test(input, expected, tzinfo)
            self.assertEquals(time.resolution, datetime.timedelta(minutes=1))

        # 'now' is Monday, 2004-12-06 14:15:16 UTC
        testDay('yesterday',       '2004-12-05')
        testDay(' ToDaY ',         '2004-12-06')
        testDay('   TuESDaY ',     '2004-12-07')
        testDay(' ToMoRroW ',      '2004-12-07')
        testDay('wednesday',       '2004-12-08')
        testDay('This wednesday',  '2004-12-08')
        testDay('neXt wednesday',  '2004-12-08')
        testDay('thursday',        '2004-12-09')
        testDay('friday',          '2004-12-10')
        testDay('saturday',        '2004-12-11')
        testDay('sunday',          '2004-12-12')
        testDay('sunday',          '2004-12-12', self.MST())     # timezone is insignificant for dates with resolution >= 1 day
        testDay('monday',          '2004-12-13')

        testMinute('15:00',        '2004-12-06T15:00+00:00')
        testMinute('8:00',         '2004-12-06T15:00+00:00', self.MST())
        testMinute(' 14:00  ',     '2004-12-07T14:00+00:00')
        testMinute(' 2:00  pm ',   '2004-12-07T14:00+00:00')
        testMinute(' 02:00  pm ',  '2004-12-07T14:00+00:00')
        testMinute(' noon ',       '2004-12-07T12:00+00:00')
        testMinute('midnight',     '2004-12-07T00:00+00:00')

        testMalformed('24:01')
        testMalformed('24:00')  # this one might be considered valid by some people, but it's just dumb.
        testMalformed('13:00pm')
        testMalformed('13:00am')

        # these are perfectly reasonable cases, but are totally broken. Good enough for demo work.
        testMalformed('13:00 tomorrow')
        testMalformed('13:00 next thursday')
        testMalformed('last monday')

    def testFromISO8601DateAndTime(self):
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-06T14:15:16') )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('20041206T141516') )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('20041206T091516-0500') )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-06T07:15:16', self.MST()) )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-06T14:15:16Z', self.MST()) )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-06T14:15:16-0000', self.MST()) )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-06T14:15:16-0000') )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-W50-1T14:15:16') )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-341T14:15:16') )

        self.assertRaises( ValueError, extime.Time.fromISO8601TimeAndDate, '2005-W53' )
        self.assertRaises( ValueError, extime.Time.fromISO8601TimeAndDate, '2004-367' )
        try:
            extime.Time.fromISO8601TimeAndDate('2004-366')
        except ValueError:
            raise unittest.FailTest, 'leap years should have 366 days'

        try:
            extime.Time.fromISO8601TimeAndDate('2004-123T14-0600')
            extime.Time.fromISO8601TimeAndDate('2004-123T14:13-0600')
            extime.Time.fromISO8601TimeAndDate('2004-123T14:13:51-0600')
        except ValueError:
            raise unittest.FailTest, 'timezone should be allowed if time with *any* resolution is specified'

        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2005').resolution, datetime.timedelta(days=365) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004').resolution, datetime.timedelta(days=366) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02').resolution, datetime.timedelta(days=29) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29').resolution, datetime.timedelta(days=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13').resolution, datetime.timedelta(hours=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13:10').resolution, datetime.timedelta(minutes=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13:10:05').resolution, datetime.timedelta(seconds=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13:10:05.010').resolution, datetime.timedelta(microseconds=1000) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13:10:05.010000').resolution, datetime.timedelta(microseconds=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-02-29T13:10:05.010000123').resolution, datetime.timedelta(microseconds=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-W11').resolution, datetime.timedelta(days=7) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-W11-3').resolution, datetime.timedelta(days=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-W11-3T14:16:21').resolution, datetime.timedelta(seconds=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-123').resolution, datetime.timedelta(days=1) )
        self.assertEquals( extime.Time.fromISO8601TimeAndDate('2004-123T14:16:21').resolution, datetime.timedelta(seconds=1) )

    def testFromStructTime(self):
        self._checkReference( extime.Time.fromStructTime((2004, 12, 6, 14, 15, 16, 0, 0, 0)) )
        self._checkReference( extime.Time.fromStructTime((2004, 12, 6, 7, 15, 16, 0, 0, 0), self.MST()) )
        self._checkReference( extime.Time.fromStructTime((2004, 12, 6, 15, 15, 16, 0, 0, 0), self.CET()) )
        self._checkReference( extime.Time.fromStructTime(time.struct_time((2004, 12, 6, 7, 15, 16, 0, 0, 0)), self.MST()) )

    def testFromDatetime(self):
        self._checkReference( extime.Time.fromDatetime(datetime.datetime(2004, 12, 6, 14, 15, 16)) )
        self._checkReference( extime.Time.fromDatetime(datetime.datetime(2004, 12, 6, 7, 15, 16, tzinfo=self.MST())) )
        self._checkReference( extime.Time.fromDatetime(datetime.datetime(2004, 12, 6, 15, 15, 16, tzinfo=self.CET())) )

    def testFromPOSIXTimestamp(self):
        self._checkReference( extime.Time.fromPOSIXTimestamp(extime.mkgmtime((2004, 12, 6, 14, 15, 16, 0, 0, 0))) )

    def testFromRFC2822(self):
        self._checkReference( extime.Time.fromRFC2822('Mon, 6 Dec 2004 14:15:16 -0000') )
        self._checkReference( extime.Time.fromRFC2822('Mon, 6 Dec 2004 9:15:16 -0500') )
        self._checkReference( extime.Time.fromRFC2822('6   Dec   2004   9:15:16   -0500') )
        self._checkReference( extime.Time.fromRFC2822('Mon,6 Dec 2004 9:15:16 -0500') )
        self._checkReference( extime.Time.fromRFC2822('Mon,6 Dec 2004 9:15 -0500'), datetime.datetime(2004, 12, 6, 14, 15) )
        self._checkReference( extime.Time.fromRFC2822('Mon,6 Dec 2004 9:15:16 EST') )
        self._checkReference( extime.Time.fromRFC2822('Monday,6 December 2004 9:15:16 EST') )
        self.assertRaises( ValueError, extime.Time.fromRFC2822, 'some invalid date' )

    def testObsoleteRFC2822(self):
        self._checkReference( extime.Time.fromRFC2822('Monday,6 December (i hate this month) 2004 9:15:16 R') )

    testObsoleteRFC2822.todo = '''\
    email.Utils implementation does not handle obseleted military style
    timezones, nor does it handled obseleted comments in the header'''

    def testAsPOSIXTimestamp(self):
        self.assertEquals( self._createReference().asPOSIXTimestamp(), 1102342516 )

    def testAsRFC2822(self):
        self.assertEquals( self._createReference().asRFC2822(), 'Mon, 6 Dec 2004 14:15:16 -0000' )
        self.assertEquals( self._createReference().asRFC2822(self.MST()), 'Mon, 6 Dec 2004 07:15:16 -0700' )
        self.assertEquals( self._createReference().asRFC2822(self.CET()), 'Mon, 6 Dec 2004 15:15:16 +0100' )

    def testAsISO8601TimeAndDate(self):
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(),
            '2004-12-06T14:15:16+00:00' )
        self.assertEquals(
            self._createReference(reference=datetime.datetime(2004, 12, 6, 14, 15, 16, 43210)).asISO8601TimeAndDate(),
            '2004-12-06T14:15:16.04321+00:00' )
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(tzinfo=self.MST()),
            '2004-12-06T07:15:16-07:00' )
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(tzinfo=self.CET()),
            '2004-12-06T15:15:16+01:00' )
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(includeTimezone=False),
            '2004-12-06T14:15:16' )
        self.assertEquals(
            self._createReference(reference=datetime.datetime(2004, 12, 6, 14, 15, 16, 43210)).asISO8601TimeAndDate(includeTimezone=False),
            '2004-12-06T14:15:16.04321' )
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(tzinfo=self.MST(), includeTimezone=False),
            '2004-12-06T07:15:16' )
        self.assertEquals(
            self._createReference().asISO8601TimeAndDate(tzinfo=self.CET(), includeTimezone=False),
            '2004-12-06T15:15:16' )

    def testAsStructTime(self):
        self.assertEquals( self._createReference().asStructTime(), (2004, 12, 06, 14, 15, 16, 0, 341, 0) )
        self.assertEquals( self._createReference().asStructTime(tzinfo=self.MST()), (2004, 12, 06, 7, 15, 16, 0, 341, 0) )
        self.assertEquals( self._createReference().asStructTime(tzinfo=self.CET()), (2004, 12, 06, 15, 15, 16, 0, 341, 0) )

    def testAsNaiveDatetime(self):
        def ref(tzinfo):
            return self.awareReference.astimezone(tzinfo).replace(tzinfo=None)

        self.assertEquals( self._createReference().asNaiveDatetime(), self.reference )
        self.assertEquals( self._createReference().asNaiveDatetime(tzinfo=self.MST()), ref(self.MST()))
        self.assertEquals( self._createReference().asNaiveDatetime(tzinfo=self.CET()), ref(self.CET()))

    def testAsDatetime(self):
        self.assertEquals( self._createReference().asDatetime(), self.awareReference )
        self.assertEquals( self._createReference().asDatetime(tzinfo=self.MST()), self.awareReference )
        self.assertEquals( self._createReference().asDatetime(tzinfo=self.CET()), self.awareReference )

    def testAsHumanly(self):
        self.assertEquals(
            self._createReference().asHumanly(now=extime.Time.fromStructTime((2004, 12, 6, 14, 15, 16, 0, 0, 0))),
            '02:15 pm' )
        self.assertEquals(
            self._createReference().asHumanly(tzinfo=self.MST(), now=extime.Time.fromStructTime((2004, 12, 6, 14, 15, 16, 0, 0, 0))),
            '07:15 am' )
        self.assertEquals(
            self._createReference().asHumanly(tzinfo=self.CET(), now=extime.Time.fromStructTime((2004, 12, 6, 14, 15, 16, 0, 0, 0))),
            '03:15 pm' )

        self.assertEquals(
            self._createReference().asHumanly(now=extime.Time.fromStructTime((2005, 12, 6, 14, 15, 16, 0, 0, 0))),
            '6 Dec 04, 02:15 pm' )
        self.assertEquals(
            self._createReference().asHumanly(tzinfo=self.MST(), now=extime.Time.fromStructTime((2005, 12, 6, 14, 15, 16, 0, 0, 0))),
            '6 Dec 04, 07:15 am' )
        self.assertEquals(
            self._createReference().asHumanly(tzinfo=self.CET(), now=extime.Time.fromStructTime((2005, 12, 6, 14, 15, 16, 0, 0, 0))),
            '6 Dec 04, 03:15 pm' )

        allDay = extime.Time.fromISO8601TimeAndDate('2005-123')
        self.assertEquals(allDay.asHumanly(now=allDay), 'all day')

    def testInverse(self):
        for style in [
        'POSIXTimestamp',
        'Datetime',
        'RFC2822',
        'StructTime',
        'ISO8601TimeAndDate']:
            parse = getattr(extime.Time, 'from'+style)
            format = getattr(extime.Time, 'as'+style)
            self.assertEquals( self._createReference(), parse(format(self._createReference())), '%s() is not the inverse of %s()' % (style, style))

    def testEvalRepr(self):
        evalns = {'datetime': datetime,
                  'extime': extime}
        now = extime.Time()
        self.assertEquals( now, eval(repr(now), evalns, evalns) )

    def testContainment(self):
        makeTime = extime.Time.fromISO8601TimeAndDate

        self.assertIn(makeTime('2004-05'), makeTime('2004'))
        self.assertNotIn(makeTime('2005-01'), makeTime('2004'))

    def testArithmetic(self):
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-03T14:15:16') + datetime.timedelta(days=3) )
        self._checkReference( extime.Time.fromISO8601TimeAndDate('2004-12-09T14:15:16') - datetime.timedelta(days=3) )

    def testOneDay(self):
        day = self._createReference().oneDay()
        self.assertEquals(day._time, datetime.datetime(2004, 12, 6, 0, 0, 0))
        self.assertEquals(day.resolution, datetime.timedelta(days=1))

    def testIsAllDay(self):
        self.failIf(self._createReference().isAllDay())
        self.failUnless(extime.Time.fromISO8601TimeAndDate('2005-123').isAllDay())

